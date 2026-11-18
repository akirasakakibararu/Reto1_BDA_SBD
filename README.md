# ¿Dónde pueden vivir los jóvenes en Euskadi?

Proyecto intermodular SBD + BDA para comparar el alquiler municipal con el
salario neto juvenil oficial por territorio histórico. La renta adulta de
Udalmap se conserva como contexto separado y no sustituye al salario.

## Entorno

Se ha configurado el workspace con el entorno Conda `IA`, Python 3.12.16. En PowerShell se puede ejecutar explícitamente con:

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m pip install -r requirements.txt
```

MongoDB se conecta por defecto a `mongodb://localhost:27017`. Los parámetros de Kafka y WebHDFS se leen desde `.env` (ignorado por Git); `.env.example` contiene solo valores de ejemplo. En esta revisión se verificaron las integraciones reales con los parámetros facilitados para el reto.

## Flujo del proyecto

1. Descargar EMAL, Udalmap y el PDF oficial de Indicadores de Juventud a
   `datos/originales/`, conservando metadatos y SHA-256.
2. Normalizar y validar las fuentes en `datos/procesados/`; extraer por separado
   los indicadores 31, 32 y 49 del PDF con `pypdf`.
3. Cargar en MongoDB alquileres, población, renta adulta complementaria,
   salarios juveniles territoriales y referencias del Observatorio.
4. Ejecutar consultas, CRUD, agregaciones, explain e indicadores.
5. Exportar las tablas y generar gráficos desde los resultados de MongoDB.
6. Usar los scripts de Kafka y HDFS tras configurar esos servicios. La última
   revisión verificó una carga/recuperación real en WebHDFS y un flujo de prueba
   Kafka → MongoDB con anuncios expresamente simulados.

## Ejecución local

Desde la raíz del proyecto, en PowerShell:

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m pip install -r requirements.txt
& $PY -m scripts.extraccion.descargar_alquiler
& $PY -m scripts.extraccion.descargar_renta
& $PY -m scripts.extraccion.descargar_poblacion
& $PY -m scripts.extraccion.descargar_indicadores_juventud
& $PY -m scripts.extraccion.descargar_api_indicadores_juventud
& $PY -m scripts.procesamiento.normalizar_datos
& $PY -m scripts.procesamiento.normalizar_indicadores_juventud
& $PY -m scripts.extraccion.descargar_api_renta_udalmap
& $PY -m scripts.extraccion.scrapear_renta_udalmap
& $PY -m scripts.mongodb.cargar_datos
& $PY -m scripts.mongodb.cargar_indicadores_juveniles
& $PY -m scripts.mongodb.demostrar_crud
& $PY -m scripts.mongodb.rendimiento_consistencia
& $PY -m scripts.analisis.ejecutar_analisis
& $PY -m unittest discover -s tests -v
```

MongoDB usa `mongodb://localhost:27017` y la base `reto_vivienda` por defecto. En un entorno nuevo, copie `.env.example` solo si aún no existe `.env` y ajuste los parámetros propios; no sobrescriba el archivo local ya configurado. Las descargas omiten archivos locales que ya pasan la comprobación SHA-256; añada `--force` al descargador para actualizarlo.

Kafka y HDFS se ejecutaron contra los servicios proporcionados: WebHDFS verificó 28 archivos subidos y la recuperación de un CSV por tamaño/SHA-256; Kafka entregó dos mensajes simulados que se persistieron en MongoDB con el offset confirmado. Consulte [integraciones](documentacion/integraciones.md) para el detalle, las evidencias y los comandos.

## Resultados comprobados

- Comparación juvenil principal de 2024: 72 municipios con alquiler EMAL válido,
  salario territorial 18–34 y población municipal.
- La tabla EMAL 2024 contiene 73 municipios; Mutriku se excluye porque su renta
  mensual aparece nula, sin imputaciones.
- Los salarios oficiales de 2024 son 1.487 EUR en Álava, 1.585 EUR en Bizkaia y
  1.555 EUR en Gipuzkoa. Se asignan mediante código territorial y no representan
  salarios observados por municipio.
- Los 72 municipios superan el umbral analítico del 30 %; esto no demuestra por
  sí solo imposibilidad de emancipación. El remanente calculado no incluye otros
  gastos de vida.
- Los indicadores territoriales propios quedan entre 0,87 y 1,22 puntos
  porcentuales por encima del indicador 49 del Observatorio; las diferencias de
  cobertura y metodología están documentadas.
- Se cargaron 135 observaciones salariales y 123 referencias de los indicadores
  32 y 49, preservando los márgenes de territorio, edad y sexo sin combinarlos.
- Las tablas JSON oficiales del Observatorio para los indicadores 31, 32 y 49
  se descargaron y contrastaron con sus valores publicados. El PDF se mantiene
  como fuente de normalización; la respuesta JSON se conserva como validación.
- La API REST oficial de Udalmap contrastó 4.031 registros (la única observación ausente es nula en el CSV); el scraping HTML contrastó los 4.032 registros disponibles.
- La comparación adulta de 2023 sigue disponible como análisis complementario,
  no como sustituto del salario juvenil. También se conserva la serie histórica
  de alquiler 2016–2025.
- Se ejecutaron 5 consultas y 6 pipelines de MongoDB, indicadores adultos y
  juveniles, y nueve gráficos en total.
- La comprobación de rendimiento produjo `COLLSCAN` con 740 documentos examinados y `IXSCAN` con 22 en la consulta de alquileres bajo 600 € (el conjunto devuelve 22 resultados sin límite).
- La integración real WebHDFS cargó 18 archivos originales y 10 procesados; el listado remoto mostró 28 archivos en 9 directorios. Se recuperó `salarios_juveniles_observatorio.csv` y su SHA-256 coincidió con el original procesado.
- La integración real Kafka creó el tópico del proyecto; dos anuncios de prueba simulados se consumieron y guardaron en `anuncios_stream` como `Decimal128`. Los offsets 0 y 1 quedaron confirmados (siguiente offset del grupo: 2). No son datos inmobiliarios reales ni alteran los indicadores.
- Las tablas, gráficos, indicadores y limitaciones están en `resultados/` y
  [resultados y conclusiones](documentacion/resultados.md). La evidencia de la
  ejecución BDA se conserva en
  [verificacion_integraciones_bda.json](resultados/tablas/verificacion_integraciones_bda.json);
  el estado de validación se detalla en
  [revisión de entregables](documentacion/estado_entregables.md).

## Documentación

- [Fuentes de datos](documentacion/fuentes_datos.md)
- [Arquitectura](documentacion/arquitectura.md)
- [Metodología](documentacion/metodologia.md)
- [Modelo MongoDB](documentacion/modelo_mongodb.md)
- [Integraciones Kafka/HDFS](documentacion/integraciones.md)
- [Resultados y conclusiones](documentacion/resultados.md)
- [Revisión de entregables](documentacion/estado_entregables.md)

## Autores

Proyecto realizado por:

- Akira Sakakibara
- Alvaro Morcillo
- Iker Bilbao
