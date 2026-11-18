# Revisión final de entregables

Estado conforme al guion y a los criterios detallados en el enunciado del reto. “Comprobado” significa que se ejecutó en este equipo con los datos y servicios disponibles. Kafka y WebHDFS se conectaron con los parámetros facilitados y las operaciones descritas se verificaron contra los servicios reales.

| Criterio del PDF | Estado | Ejecución real y evidencia | Pendiente |
|---|---|---|---|
| BDA — Extracción de datos mediante Python | Completado y ejecutado | Descargas XLSX/CSV, API REST JSON, scraping HTML y PDF oficial de juventud automatizados; el portal oficial del Observatorio devolvió tres respuestas JSON HTTP 200 cuyos valores clave se contrastaron con el PDF. El extractor PDF verificó 135 salarios y 123 referencias de los indicadores 32/49. Udalmap/API/HTML contrastados. | El endpoint JSON del portal OVJ no está documentado como API independiente y puede cambiar; el PDF preservado sigue siendo la fuente de normalización. |
| BDA — Almacenamiento HDFS | Completado y ejecutado | WebHDFS recibió 18 archivos originales y 10 procesados; se listaron 28 archivos en 9 directorios. Se recuperó un CSV y se verificó igualdad de tamaño y SHA-256. Evidencia: `logs/hdfs.log` y `datos/recuperados/verificacion_salarios_juveniles_hdfs.csv`. | La conexión depende de la disponibilidad futura del servicio y de configurar `.env` en otro entorno. |
| BDA — Kafka | Completado y ejecutado | Se creó el tópico del proyecto. Dos anuncios simulados se publicaron y consumieron; ambos se persistieron en `anuncios_stream` como `Decimal128`. Partición 0: offsets 0 y 1 confirmados; offset comprometido siguiente: 2. Evidencia: `logs/kafka.log`. | Solo se probaron eventos simulados; no hay anuncios reales ni flujo de negocio conectado. |
| BDA — Integración | Completado y ejecutado | Se verificó el flujo Kafka → consumidor → MongoDB, incluida la persistencia del documento antes de confirmar el offset. | La ejecución futura requiere el broker, MongoDB y parámetros disponibles. |
| SBD RA1 — Integración de fuentes | Completado y ejecutado | EMAL, población municipal y salario juvenil territorial relacionados por códigos y año; renta adulta Udalmap permanece complementaria. | Sin dato salarial por municipio/edad; se usa salario territorial observado. |
| SBD RA1 — Construcción del conjunto de datos | Completado y comprobado | Cinco colecciones analíticas principales: `municipios`, `alquileres`, `socioeconomicos`, `salarios_juveniles` y `referencias_juventud`; `anuncios_stream` se mantiene separada para eventos Kafka simulados. Modelo descrito en [documentación](modelo_mongodb.md). | No hay salarios juveniles municipales en la fuente pública verificada. |
| SBD RA1 — Limpieza y transformación con PyMongo | Completado y ejecutado | Transformación anterior más 135 salarios y 123 referencias cargadas como `Decimal128`; cero dimensiones duplicadas y cero medidas no decimales. Mutriku 2024 se conserva como nulo, sin imputar. | Ninguno para las fuentes procesadas. |
| SBD RA1 — Automatización de carga y tratamiento | Completado y ejecutado | Scripts repetibles para normalizar, cargar por upsert y verificar; dos cargas sin duplicados. | Ninguno. |
| SBD RA3 — Modelado MongoDB | Completado y comprobado | Tipos BSON adecuados, claves estables y decisión de referencing justificada. | Ninguno. |
| SBD RA3 — CRUD con PyMongo | Completado y comprobado | Create, Read, Update y Delete verificados por código en colección temporal, eliminada al finalizar. | Ninguno. |
| SBD RA3 — Consultas | Completado y ejecutado | Cinco consultas útiles con filtros, comparación, lógica, proyección, ordenación y campos anidados. | Ninguno. |
| SBD RA3 — Aggregation Pipeline | Completado y ejecutado | Seis pipelines; los nuevos enlazan salario y benchmark por código territorial/año y renta/población por código municipal/año. | Ninguno. |
| SBD RA3 — Índices y rendimiento | Completado y ejecutado | `COLLSCAN`: 740 documentos; `IXSCAN`: 22 documentos y claves; ambos devuelven 22. Evidencia en [explain](../resultados/tablas/explain_indices.json). | La latencia varía según datos, caché y hardware. |
| SBD RA3 — Consistencia | Completado y ejecutado | `update_one` con `$inc` verificado; se justifica por qué no hace falta una transacción multidocumento. Evidencia en [operación atómica](../resultados/tablas/operacion_atomica.json). | Ninguno. |
| SBD RA4 — Datos heterogéneos | Completado y ejecutado | XLSX, CSV, JSON, HTML y PDF se normalizan; el PDF se extrae con `pypdf` y se conserva con hash/metadatos. | Ninguno. |
| SBD RA4 — Automatización del análisis | Completado y ejecutado | Un punto de entrada ejecuta consultas, agregaciones, indicadores, exportaciones y gráficos. | Requiere MongoDB local y colecciones cargadas. |
| SBD RA4 — Indicadores | Completado y ejecutado | Indicadores juveniles de esfuerzo, remanente, umbral 30 % y diferencia; comparación territorial y contraste OVJ. El análisis adulto queda separado. | Umbral 30 % analítico; no prueba asequibilidad individual. |
| SBD RA4 — Respuesta al reto | Completado con limitaciones documentadas | 72 municipios con alquiler válido de 2024; 73 registros EMAL, pero Mutriku tiene renta nula. Todos los cocientes superan 30 %; no equivale a declarar inviabilidad individual. | La fuente juvenil solo ofrece salario por territorio, no por municipio. |
| SBD RA4 — Preparación para visualización | Completado y ejecutado | Exportación de tablas y cinco gráficos juveniles; se mantienen cuatro gráficos adultos/históricos. | Ninguno. |
| Documentación, entorno y pruebas | Completado y ejecutado | Python 3.12.16; compilación, 19 pruebas unitarias, validación de CSV/JSON, colecciones MongoDB y ejecución real de Kafka/WebHDFS. | La reproducibilidad de servicios externos depende de su disponibilidad y configuración local. |

## Resumen de lo que falta

El sistema analítico y las integraciones se ejecutaron. Para repetir la demostración en otro entorno:

1. Configurar un broker Kafka accesible y MongoDB; crear el tópico y ejecutar consumidor/productor simulado.
2. Configurar WebHDFS; ejecutar `init`, carga, listado, recuperación y verificación contra el cluster.
Las ejecuciones de esta revisión sí generaron mensajes consumidos y archivos verificados en HDFS; los mensajes son solo datos de prueba. Consulte [integraciones](integraciones.md) para comandos y evidencias. Los resultados cuantitativos y sus limitaciones se explican en [resultados y conclusiones](resultados.md).
