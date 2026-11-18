# Resultados y conclusiones

## Comparación juvenil principal: año 2024

La comparación combina el alquiler EMAL municipal de 2024, el salario neto juvenil territorial del indicador 31 del Observatorio Vasco de la Juventud y la población municipal Udalmap de 2024. Los salarios aplicados a cada municipio son medias de su territorio histórico, no observaciones salariales municipales.

EMAL contiene 73 registros de municipios con geografía actual para 2024. La renta mensual de Mutriku (`20056`) es nula, por lo que se excluye sin imputación. El análisis compara **72 municipios** con alquiler positivo; no extrapola a los municipios sin cobertura de EMAL.

### Indicadores principales

| Indicador | Definición |
|---|---|
| Alquiler mensual | Media mensual por contrato de EMAL |
| Salario neto juvenil | Indicador 31: personas asalariadas de 18–34 años, extras prorrateadas; salario de su territorio |
| Esfuerzo | `alquiler mensual / salario neto mensual × 100` |
| Dinero restante | `salario neto mensual − alquiler mensual` |
| Máximo de referencia | `salario neto mensual × 0,30` |
| Exceso sobre el máximo de referencia | `alquiler mensual − máximo de referencia` |

El 30 % es un umbral analítico de referencia, no una garantía de emancipación. El remanente no descuenta suministros, alimentación, transporte, fianza ni otros gastos.

### Menor y mayor esfuerzo estimado entre los 72 municipios analizados

El orden refleja el alquiler municipal dividido por el salario medio territorial asignado. No debe interpretarse como una clasificación del salario propio de cada municipio.

| Municipio | Territorio | Alquiler mensual | Salario territorial | Alquiler / salario | Resto tras alquiler |
|---|---|---:|---:|---:|---:|
| Ondarroa | Bizkaia | 543,44 EUR | 1.585 EUR | **34,29 %** | 1.041,56 EUR |
| Markina-Xemein | Bizkaia | 564,67 EUR | 1.585 EUR | **35,63 %** | 1.020,33 EUR |
| Zumarraga | Gipuzkoa | 569,07 EUR | 1.555 EUR | **36,60 %** | 985,93 EUR |
| Zarautz | Gipuzkoa | 965,15 EUR | 1.555 EUR | **62,07 %** | 589,85 EUR |
| Getxo | Bizkaia | 1.021,74 EUR | 1.585 EUR | **64,46 %** | 563,26 EUR |
| Donostia / San Sebastián | Gipuzkoa | 1.121,71 EUR | 1.555 EUR | **72,14 %** | 433,29 EUR |

En los 72 municipios el esfuerzo estimado supera el 30 %. En ninguno el salario medio territorial resulta inferior al alquiler medio mensual, pero el remanente positivo no cubre por sí solo todos los gastos de vida. Por tanto, los datos muestran una presión elevada del alquiler y no permiten afirmar que cada joven pueda o no pueda emanciparse.

### Contraste por territorio histórico

El cálculo propio pondera los alquileres medios municipales por el número de fianzas EMAL y los divide por el salario territorial oficial. El contraste usa el indicador 49 publicado por el Observatorio.

| Código territorial | Territorio | Municipios incluidos | Alquiler ponderado | Salario juvenil | Cálculo propio | Indicador 49 OVJ | Diferencia |
|---|---|---:|---:|---:|---:|---:|---:|
| `01` | Álava | 4 | 764,58 EUR | 1.487 EUR | 51,42 % | 50,20 % | +1,22 pp |
| `20` | Gipuzkoa | 33 | 868,93 EUR | 1.555 EUR | 55,88 % | 54,90 % | +0,98 pp |
| `48` | Bizkaia | 35 | 828,49 EUR | 1.585 EUR | 52,27 % | 51,40 % | +0,87 pp |

La cercanía de los valores sirve como contraste de plausibilidad, no como identidad metodológica. El cálculo propio se limita a municipios con tabla anual EMAL publicada y con renta positiva; el Observatorio calcula su indicador a partir de los importes medios de las fianzas depositadas y puede utilizar cobertura territorial más amplia. También pueden influir las reglas de ponderación y las actualizaciones/provisionalidad indicadas por EMAL.

### Diferencias por edad y contexto de renta

Los dos grupos de edad coincidentes entre los indicadores 31 y 49 se publican para Euskadi, no por territorio ni municipio:

| Grupo de edad | Salario neto mensual medio | Indicador 49: esfuerzo oficial de alquiler |
|---|---:|---:|
| 18–29 | 1.381 EUR | 59,4 % |
| 30–34 | 1.774 EUR | 46,2 % |

El indicador 49 también publica 18–24 (69,4 %) y 25–29 (53,5 %), pero el indicador 31 no ofrece salarios con esos mismos dos cortes. Esos pares no se han combinado.

El indicador 32 publica renta personal media anual de jóvenes de 25–29 años: 17.930 EUR en 2023 (19.076 EUR para hombres y 16.734 EUR para mujeres). Esta renta incluye diversas fuentes y no es salario neto; se conserva como contexto separado.

## Fuentes, almacenamiento y validaciones

- El PDF oficial se descargó con HTTP 200, se preservó sin modificar y se verificó con SHA-256. El extractor `pypdf` obtuvo 135 observaciones del indicador 31 y 123 referencias de los indicadores 32 y 49. Comprobó periodos, estructura de las filas y valores publicados de 2024/2023.
- El portal estadístico oficial devolvió HTTP 200 para las tablas JSON de los indicadores 31, 32 y 49. Los valores salariales de 2024, las referencias de alquiler de 2024 y la renta personal de 2023 comprobados coinciden con el PDF. El portal también muestra renta personal juvenil 2024 (20.109 EUR total); se conserva en el original JSON, pero no se mezcla con la serie normalizada de la edición PDF ni se usa como salario. Evidencia: [informe de verificación del portal](../datos/procesados/ingresos/verificacion_api_indicadores_juventud.json).
- La interfaz ofrece exportación Excel, pero el ensayo de descarga automatizada produjo un libro sin celdas de datos. Se usa el endpoint JSON de la aplicación para la comprobación independiente; al no ser una API documentada, el PDF sigue siendo la referencia archivística y la fuente cargada en MongoDB.
- En MongoDB local se cargaron 135 documentos en `salarios_juveniles` y 123 en `referencias_juventud`. Los códigos territoriales oficiales usados son `01` Álava, `20` Gipuzkoa y `48` Bizkaia. Las dimensiones de edad/sexo se guardan por separado y no hay observaciones edad × territorio inventadas.
- Los salarios y las referencias monetarias se almacenan como `Decimal128`. Los índices únicos y la validación detectaron cero duplicados y cero medidas con tipo no decimal.
- La agregación juvenil enlaza territorio y año para el salario; población se enlaza por código municipal y año. La salida contiene 72 filas municipales, 3 territorios y 2 grupos de edad.
- La API REST de Udalmap contrastó 4.031 registros y el scraping de la tabla HTML contrastó 4.032 filas; ambos son controles independientes del CSV canónico.
- Se mantiene el análisis socioeconómico anterior de 2023 con renta disponible adulta de Udalmap. No se usa como sustituto del salario juvenil.
- Las series históricas de alquiler 2016–2025 y sus resultados siguen disponibles.
- Se ejecutan 5 consultas y 6 pipelines de MongoDB; se mantienen las comprobaciones CRUD, de índices, `explain` y actualización atómica del proyecto.

## Integraciones BDA verificadas en servicios reales

Las integraciones se ejecutaron con los parámetros de conexión facilitados para esta revisión; no se incluyen en el repositorio las variables locales de `.env`.

- **WebHDFS:** se subieron 18 archivos bajo `originales/` y 10 bajo `procesados/`, incluidos sus metadatos. El listado remoto devolvió 28 archivos en 9 directorios. Se recuperó [el CSV de salarios juveniles](../datos/recuperados/verificacion_salarios_juveniles_hdfs.csv) (8.831 bytes); su SHA-256 coincidió con el archivo local y con la copia remota. Evidencia de ejecución: `logs/hdfs.log`.
- **Kafka → MongoDB:** se creó el tópico aislado `reto_vivienda_iabd_user11`. Se publicaron y consumieron dos anuncios **simulados**; ambos quedaron en `anuncios_stream` con el alquiler como `Decimal128`. Se confirmó el offset 0 y el offset 1 de la partición 0; el offset comprometido del grupo quedó en 2. Evidencia de ejecución: `logs/kafka.log`.
- El productor simulado no extrae anuncios reales, no alimenta los indicadores EMAL y no modifica las conclusiones de emancipación. La prueba confirma conectividad, transporte, validación, persistencia y confirmación de offsets en el servicio usado para esta ejecución.
- El resumen verificable de ambas integraciones se guarda en [evidencia BDA](../resultados/tablas/verificacion_integraciones_bda.json). Las conexiones dependen de que los servicios y parámetros sigan disponibles al volver a ejecutar el proyecto.

## Gráficos y tablas generados

Gráficos juveniles de 2024:

- [Esfuerzo por los 72 municipios](../resultados/graficos/esfuerzo_alquiler_salario_juvenil_municipios_2024.png)
- [Esfuerzo: 10 municipios con menor y mayor esfuerzo](../resultados/graficos/esfuerzo_alquiler_salario_juvenil_municipios_2024_10_menores_y_10_mayores.png)
- [Dinero restante por municipio](../resultados/graficos/dinero_restante_salario_juvenil_municipios_2024.png)
- [Dinero restante: 10 municipios con menor y mayor cantidad](../resultados/graficos/dinero_restante_salario_juvenil_municipios_2024_10_menores_y_10_mayores.png)
- [Salario y alquiler por territorio](../resultados/graficos/salario_y_alquiler_juvenil_territorios_2024.png)
- [Contraste con el indicador 49](../resultados/graficos/contraste_esfuerzo_juvenil_ovj_territorios_2024.png)
- [Comparación de edades](../resultados/graficos/comparacion_juvenil_por_edad_2024.png)

Resultados descargables:

- [Indicadores municipales juveniles](../resultados/indicadores/indicadores_juveniles_municipales_2024.csv)
- [Comparación territorial y contraste OVJ](../resultados/tablas/comparativa_juvenil_territorial_2024.csv)
- [Comparación por edad](../resultados/tablas/comparativa_juvenil_edad_2024.csv)
- [Resumen automático](../resultados/indicadores/resumen_emancipacion_juvenil_2024.json)
- [Resultado de carga MongoDB](../resultados/tablas/carga_indicadores_juveniles.json)

Los cuatro gráficos anteriores de alquiler/renta adulta e historia siguen en `resultados/graficos/`; son complementarios y no protagonizan la lectura de emancipación juvenil.

## Conclusión y límites

Entre los 72 municipios analizados, Ondarroa, Markina-Xemein y Zumarraga muestran los menores cocientes entre alquiler medio y salario juvenil territorial; Donostia, Getxo y Zarautz muestran los mayores. Los 72 cocientes exceden el 30 % de referencia. Esto identifica municipios con mayor o menor presión relativa del alquiler dentro de la cobertura analizada, pero no permite afirmar una viabilidad individual: los salarios son medias territoriales de personas asalariadas, la renta puede variar por edad, sexo y situación laboral, y el alquiler EMAL no representa todo el mercado ni todos los municipios.

La transferencia/recuperación WebHDFS y el flujo Kafka → MongoDB se comprobaron realmente en esta revisión. La comparación estadística sigue limitada a los 72 municipios con alquiler EMAL válido y a salarios territoriales aplicados por código oficial; los mensajes Kafka utilizados para probar la integración son simulados.
