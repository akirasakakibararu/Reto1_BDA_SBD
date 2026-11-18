# Modelo MongoDB

## Base de datos y colecciones

Base de datos: `reto_vivienda`, en el MongoDB local configurado por `MONGODB_URI`.

| Colección | Documento/identificador | Función |
|---|---|---|
| `municipios` | `_id = municipality_code` | Referencia municipal y territorio histórico. |
| `alquileres` | `_id = código:geografía:año` | Indicadores anuales EMAL de alquiler y procedencia. |
| `socioeconomicos` | `_id = código:año` | Renta personal disponible y población por municipio/año. |
| `salarios_juveniles` | dimensión indicador-año-ámbito-territorio-edad-sexo | Salario juvenil publicado, sin duplicarlo como observación municipal. |
| `referencias_juventud` | dimensión indicador-año-ámbito-territorio-edad-sexo | Indicadores OVJ 49 y 32, con métricas y unidades diferenciadas. |
| `anuncios_stream` | `_id = event_id` | Mensajes Kafka validados; en la prueba real contiene dos anuncios expresamente simulados. |
| `operaciones_atomicas` | `_id` de la operación | Colección auxiliar para demostrar actualizaciones atómicas con `$inc`. |

Los códigos municipales se guardan como texto de cinco caracteres, incluidos los ceros iniciales. Los importes se guardan como BSON `Decimal128`; población y número de fianzas como enteros. Los valores fuente ausentes permanecen como `null`; no se imputan.

## Referencias

`alquileres.municipality_code` y `socioeconomicos.municipality_code` referencian `municipios._id`. El código más el año permite unir alquiler con los indicadores socioeconómicos; se conserva `geography.variant` para distinguir el Galdakao actual del histórico que incluía Usansolo. El histórico no participa en comparaciones de límites actuales.

Los metadatos de origen están anidados en `source`, `reference` y `geography`. El libro de alquiler registra además las hojas originales y las filas fuente. Esta estructura facilita trazabilidad y consultas anidadas sin duplicar la serie completa dentro de cada municipio.

`salarios_juveniles` conserva los márgenes de edad, sexo y territorio tal como aparecen en el indicador 31. Los datos de 18–34 por territorio histórico usan `territory_code` de dos caracteres (`01`, `48`, `20`), `geography_level: "territory"` y `age_group: "18-34"`. Las observaciones de grupos de edad o sexo publicadas solo para Euskadi usan `geography_level: "euskadi"` y `territory_code: null`; no se crean cruces artificiales. Los salarios mensuales se guardan como BSON `Decimal128`.

`referencias_juventud` guarda el indicador 49 como `metric: "rent_access_percent"` y el indicador 32 como `metric: "personal_income_annual"`. Los valores usan `Decimal128`, pero tienen distinta unidad y definición: porcentaje de salario neto frente a renta personal anual. El indicador 32 no se usa como salario.

`anuncios_stream` es una colección técnica separada de las fuentes estadísticas. El consumidor almacena el alquiler como `Decimal128`, conserva tópico/partición/offset y utiliza `event_id` como clave idempotente. La verificación de Kafka guardó dos mensajes marcados `is_simulated: true`; no deben incorporarse a `alquileres` ni a las métricas de emancipación.

Las respuestas JSON del portal estadístico del Observatorio se archivan y validan como contraste independiente, pero no se vuelven a insertar en estas colecciones. Así se evita duplicar los indicadores que ya se normalizan desde el PDF; la actualización del indicador 32 para 2024 permanece únicamente en el original JSON y no se confunde con los registros de la edición PDF.

## Documentos representativos

```javascript
// municipios
{
  _id: "01002",
  municipality_code: "01002",
  municipality_name: "Amurrio",
  territory: { code: "01", name: "Araba/Álava" },
  source: { name: "...", file: "...", batch_id: "..." }
}

// alquileres
{
  _id: "01002:municipality:2023",
  municipality_code: "01002",
  year: 2023,
  geography: { variant: "municipality",
               included_in_current_boundary_comparison: true },
  rental: { monthly_eur: Decimal128("..."),
            per_m2_eur: Decimal128("..."), annual_eur: Decimal128("..."),
            deposit_count: 81},
  reference: { rent_reference: "EMAL contract start year" },
  source: { name: "EMAL - alquiler municipal",
            sheets: ["T2.1", "T2.2", "T2.3"], batch_id: "..." }
}

// socioeconomicos
{
  _id: "01002:2023",
  municipality_code: "01002",
  year: 2023,
  indicators: { available_income_eur: Decimal128("..."),
                available_income_monthly_eur: Decimal128("..."),
                population: 10500 },
  source: { available_income: { name: "...", source_row: 42 },
            population: { name: "...", source_row: 42 }, batch_id: "..." }
}
```

```javascript
// salarios_juveniles: media territorial, no un salario municipal
{
  _id: "31:2024:territory:01:18-34:total",
  indicator_code: 31,
  year: 2024,
  geography_level: "territory",
  territory_code: "01",
  territory_name: "Álava",
  age_group: "18-34",
  sex: "total",
  net_monthly_salary_eur: Decimal128("1487"),
  unit: "EUR/month",
  source: { name: "Observatorio Vasco de la Juventud",
            indicator_code: 31, source_page: 69, url: "...", sha256: "..." }
}

// referencias_juventud: indicador 49 de contraste
{
  _id: "49:2024:territory:01:18-34:total",
  indicator_code: 49,
  year: 2024,
  geography_level: "territory",
  territory_code: "01",
  territory_name: "Álava",
  age_group: "18-34",
  sex: "total",
  metric: "rent_access_percent",
  value: Decimal128("50.2"),
  unit: "percent",
  source: { name: "Observatorio Vasco de la Juventud",
            indicator_code: 49, source_page: 91, url: "...", sha256: "..." }
}
```

Los valores de ejemplo con puntos suspensivos son esquemáticos, no resultados. La carga se realiza mediante `ReplaceOne(..., upsert=True)` y conserva un `batch_id` derivado de los SHA-256 de los originales. Las colecciones no se vacían antes de cargar: se actualizan por clave estable y solo se retiran documentos antiguos que el propio cargador marcó como importaciones previas.

Después de cada upsert, `cargar_datos.py` usa pipelines `update_many` de PyMongo para materializar ausentes como nulos, normalizar tipos BSON, calcular `rental.annual_eur` y `indicators.available_income_monthly_eur`, y verificar que no haya campos derivados ausentes. `cargar_indicadores_juveniles.py` verifica el SHA-256 del PDF, convierte magnitudes a `Decimal128` y aplica índices únicos a sus dimensiones. Los upserts detectan/impiden duplicados; la etapa de validación agrupa por claves de negocio y falla si encuentra alguno.

La agregación principal une `alquileres` con `municipios` para obtener el código territorial, enlaza `salarios_juveniles` por código territorial y año, y enlaza población desde `socioeconomicos` por código municipal y año. Nunca replica el salario territorial en la colección de alquileres ni lo presenta como observado específicamente en ese municipio.
