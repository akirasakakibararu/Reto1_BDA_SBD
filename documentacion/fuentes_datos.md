# Fuentes de datos

Investigación de fuentes realizada el 13/11/2026. Se priorizan conjuntos oficiales, municipales, automatizables y con un identificador territorial común.

## Alquiler: Estadística del Mercado de Alquiler (EMAL)

- **Responsable:** Departamento de Vivienda y Agenda Urbana del Gobierno Vasco.
- **Catálogo y descargas:** [Tablas estadísticas EMAL](https://opendata.euskadi.eus/catalogo/-/estadistica/tablas-estadisticas-de-la-estadistica-del-mercado-de-alquiler-emal-2016-2020-hasta-el-2-trimestre-de-2020/).
- **Archivo municipal usado:** [XLSX original EMAL 2016-2026T1](https://opendata.euskadi.eus/contenidos/estadistica/122417_emal_tablas_estad/opendata/EMAL.-Barrios-Municipios.-2016-2026_es.xlsx).
- **Metodología:** [Ficha metodológica EMAL](https://opendata.euskadi.eus/ficha-metodologica-de-la-estadistica-del-mercado-de-alquiler-ema/webopd00-dataset/es/).
- **Acceso:** descargas públicas XLSX y ODS. La descarga XLSX de viviendas habituales colectivas fue comprobada con HTTP 200; tamaño observado: 256.980 bytes.
- **Variables:** número de fianzas depositadas, renta mensual media por contrato y renta mensual media por metro cuadrado construido.
- **Versión descargada:** el catálogo indicaba actualización el 27/10/2026 y periodo de referencia hasta 31/03/2026. La descarga local respondió HTTP 200 y conserva SHA-256 y cabeceras en su archivo `.metadata.json`.
- **Cobertura:** Euskadi; tablas de municipios de más de 5.000 habitantes y capitales. La hoja municipal observada contiene 74 filas y 73 códigos municipales únicos. También hay tablas trimestrales para un subconjunto de municipios de más de 20.000 habitantes y desgloses de capitales.
- **Periodo/frecuencia:** las series anuales municipales observadas cubren 2016–2025; el libro contiene tablas trimestrales hasta 2026-T1 para determinados municipios. La ficha metodológica describe periodicidad anual y avances semestrales; el catálogo se actualiza con mayor frecuencia.
- **Naturaleza:** estadística censal basada en fianzas depositadas de contratos registrados; no mide anuncios ni todos los tipos de vivienda.
- **Limitaciones:** el ámbito publicado excluye municipios pequeños. Las tablas incluyen la nota de que se actualiza la renta de contratos de años anteriores según el IRAV hasta la fecha de referencia. Los resultados históricos no deben describirse automáticamente como rentas nominales vigentes en el año de inicio del contrato. Los datos se marcan como provisionales en el libro descargado.
- **Cambio territorial:** Galdakao (código `48036`) aparece en dos series. Las notas del archivo distinguen Galdakao antes de la segregación de Usansolo (Galdakao + Usansolo) y después de ella (sin Usansolo). No son duplicados intercambiables.
- **Licencia:** el catálogo publica licencia CC BY 4.0.

## Ingresos: renta personal disponible de Udalmap

- **Responsable/publicación:** Udalmap, Gobierno Vasco; fuente estadística subyacente: [Estadística de Renta Personal y Familiar de Eustat](https://www.eustat.eus/estadisticas/tema_69/opt_0/temas.html).
- **Catálogo:** [Renta personal disponible (€)](https://opendata.euskadi.eus/catalogo/-/indicadores-municipales-de-sostenibilidad-renta-personal-disponible-x20ac/).
- **Ficheros y API comprobados:** [CSV del indicador 61](https://opendata.euskadi.eus/contenidos/estadistica/udalmap_indicador_61/es_def/adjuntos/indicator.csv); HTTP 200, tamaño observado: 49.544 bytes. La [API REST documentada](https://api.euskadi.eus/udalmap/indicators/61/municipalities?lang=SPANISH) devolvió JSON municipal; la especificación está en [OpenAPI Udalmap](https://opendata.euskadi.eus/contenidos/recurso_tecnico/data_apirest/es_def/adjuntos/udalmap.json). La [tabla HTML municipal](https://opendata.euskadi.eus/webopd00-dataset/es/contenidos/estadistica/udalmap_indicador_61/es_def/adjuntos/indicator.shtml) se descargó y procesó mediante scraping.
- **Definición:** renta personal disponible media de residentes de 18 y más años; unidad €/habitante. Incluye rentas del trabajo, actividades económicas, transferencias/prestaciones y capital, descontando Seguridad Social e impuestos/retenciones.
- **Cobertura:** municipios de Euskadi, con códigos municipales de cinco caracteres. El fichero incluye agregados por territorio y comarca además del detalle municipal.
- **Periodo/frecuencia:** anual; último dato observado y declarado por Udalmap: 2023. La serie contiene años anteriores no consecutivos.
- **Limitación para el reto:** es renta disponible media adulta, no salario, nómina ni dato específico de jóvenes. Se usará como aproximación socioeconómica, identificándola expresamente como tal.
- **Cambio territorial:** Usansolo (`48916`) aparece en el fichero, pero su valor de renta de 2023 está vacío. El valor de Galdakao no se repartirá entre ambos municipios.
- **Licencia:** CC BY 4.0.
- **API y scraping:** la especificación OpenAPI publica el endpoint `/udalmap/indicators/{indicatorId}/municipalities`; se usa `indicatorId=61` y `lang=SPANISH`. La API proporciona identificador/nombre municipal y series anuales. El CSV sigue siendo la entrada canónica de procesamiento; API y HTML se usan como comprobaciones independientes y no duplican colecciones en MongoDB.
- **Resultado real de API:** HTTP 200, JSON de 158.636 bytes, 252 municipios y 4.031 observaciones. Las 4.031 coinciden con el CSV; la API omite `48916` (Usansolo) en 2023, cuyo valor es nulo en el CSV. No se imputa. El JSON original y metadatos están en `datos/originales/ingresos/`; evidencia en `datos/procesados/ingresos/udalmap_renta_api_verificacion.json`.
- **Resultado real del scraping:** HTTP 200, 488.758 bytes y 252 municipios; las 4.032 combinaciones municipio-año coinciden con el CSV procesado. El HTML original y sus metadatos se conservan bajo `datos/originales/ingresos/`; evidencia en `datos/procesados/ingresos/udalmap_renta_scraping_verificacion.json`.

## Ingresos juveniles: Observatorio Vasco de la Juventud

- **Responsable:** Observatorio Vasco de la Juventud, Gobierno Vasco.
- **Documento oficial:** [Indicadores de Juventud 2025 (PDF)](https://www.gazteaukera.euskadi.eus/contenidos/noticia/txostena_panorama_2025/es_def/adjuntos/Indicadores-de-Juventud-2025.pdf).
- **Acceso y formatos comprobados:** el PDF se descargó con HTTP 200 (5.261.180 bytes) y se conserva intacto en `datos/originales/juventud/` con URL, fecha, tamaño y SHA-256. El [portal estadístico oficial del Observatorio](https://www.gazteaukera.euskadi.eus/webgaz00-ovjstat/es/ae29aConsultaWar/indicadorclasificacion/consultaIndicadores/2217?locale=es) también publica tablas interactivas para los indicadores 31, 32 y 49. La tabla dispone de una opción de exportación Excel; al probar su URL de exportación directamente, el servidor devolvió un libro vacío, por lo que no se usa ese método.
- **Acceso JSON automatizado:** la aplicación web utiliza el endpoint `POST https://www.gazteaukera.euskadi.eus/webgaz00-ovjstat/es/ae29aConsultaWar/indicadornum/cogerDatosTabla`. No es una API documentada como servicio público independiente, pero devuelve JSON HTTP 200 sin credenciales y contiene los datos de las tablas oficiales. `scripts/extraccion/descargar_api_indicadores_juventud.py` obtiene dinámicamente los identificadores de filtros y periodos desde las fichas del portal, conserva cada respuesta JSON original y sus metadatos, y valida valores publicados. El PDF sigue siendo la referencia archivística y la fuente de normalización principal; el JSON se usa como contraste reproducible porque algunas desagregaciones del portal difieren de las del informe. En concreto, la tabla web del indicador 49 presenta 18–24 y 25–29, mientras que el PDF incluye el grupo 18–29; no se sustituyen ni se cruzan esos grupos.
- **Resultados de comprobación:** los importes del portal coinciden con el PDF en los valores clave de 2024 de los indicadores 31 y 49 y en los valores de 2023 del indicador 32. El portal ya muestra también el indicador 32 para 2024 (20.109 EUR total; 21.642 hombres; 18.518 mujeres). Esa actualización se conserva en el JSON original, pero no se mezcla con la tabla normalizada del PDF ni se usa como salario.
- **Indicador 31:** salario mensual neto medio de personas asalariadas de 18–34 años, con pagas extraordinarias prorrateadas. Serie 2010–2024. Ofrece el total y sexo para Euskadi, salarios totales por territorio histórico, grupos de edad 18–29 y 30–34 para Euskadi, y una comparación con España. En 2024: Euskadi 1.564 EUR; Álava 1.487 EUR; Bizkaia 1.585 EUR; Gipuzkoa 1.555 EUR; 18–29 años 1.381 EUR; 30–34 años 1.774 EUR.
- **Nivel territorial y edades:** el PDF presenta desgloses marginales separados. El salario por territorio corresponde a 18–34; los grupos de edad y el desglose por sexo son autonómicos. No publica el cruce edad × territorio ni salarios municipales. El análisis municipal aplica el salario medio territorial de 18–34 por código oficial y lo etiqueta como referencia territorial, no como salario observado del municipio.
- **Indicador 49:** proporción del salario neto mensual necesaria para pagar individualmente una vivienda libre en alquiler, estimada a partir de importes medios de fianzas depositadas ante el Gobierno Vasco. Serie 2016–2024. En 2024: Álava 50,2 %, Bizkaia 51,4 %, Gipuzkoa 54,9 %; para Euskadi, 18–29 años 59,4 % y 30–34 años 46,2 %. Es el contraste territorial y por edad utilizado en el proyecto.
- **Indicador 32:** renta personal media anual de jóvenes de 25–29 años, no salario. En 2023: 17.930 EUR; hombres 19.076 EUR y mujeres 16.734 EUR. Se mantiene separada de los importes salariales y no se usa como sustituto de una nómina neta.
- **Limitaciones:** salario medio de personas asalariadas, no de toda la juventud; no incluye desglose municipal ni cruce territorial por edad/sexo. Las comparaciones no representan el sueldo individual de una persona concreta.
- **Datos originales y procesados:** PDF y respuestas JSON del portal, cada uno con metadatos laterales, en `datos/originales/juventud/`. `pypdf` extrae los indicadores 31, 32 y 49 del PDF a `datos/procesados/ingresos/salarios_juveniles_observatorio.csv` y `referencias_juveniles_observatorio.csv`; el JSON de contraste no se carga como observaciones duplicadas en MongoDB.

## Investigación complementaria de Eustat: renta por edad

- **Operación oficial:** [Estadística de renta personal y familiar (metodología)](https://www.eustat.eus/document/datos/fm_173402_c.html). La operación incluye variables de sexo y edad, renta del trabajo, otras rentas y renta disponible; su población estadística son personas de 18 y más años en viviendas familiares. La ficha menciona municipio como ámbito geográfico, pero ello no implica que todos los cruces se publiquen en las tablas.
- **Renta personal por edad:** la tabla oficial [Renta personal media por edad, sexo y tipo de renta, 2001–2024 (RP03)](https://www.eustat.eus/bankupx/pxweb/es/DB/-/PX_173402_crpf_rpf_rp03.px/) publica los grupos de edad y los tipos de renta (incluida la renta del trabajo) para el conjunto de Euskadi. El fichero PC-Axis oficial se pudo descargar mediante HTTP 200 desde [RP03 PC-Axis](https://www.eustat.eus/bankupx/Resources/PX/Databases/DB/PX_173402_crpf_rpf_rp03.px).
- **Territorio y sexo:** la tabla [Renta personal por ámbitos territoriales, sexo y tipo de renta, 2001–2024 (RP11S)](https://www.eustat.eus/bankupx/pxweb/es/DB/-/PX_173402_crpf_rpf_rp11s.px/) ofrece dimensiones territoriales y sexo, pero no grupo de edad.
- **Disponibilidad municipal por edad:** se revisaron el [índice del Banco de Datos de Renta Personal y Familiar](https://es.eustat.eus/banku/id_173402/indexlistaopera.html) y el [apartado municipal de renta personal](https://es.eustat.eus/udalak/tablas_banco_municipales.aspx?id=2380). La tabla con edad identificada es autonómica (RP03); las tablas territoriales/municipales consultadas no publican conjuntamente municipio y edad. No se encontró, por tanto, un salario juvenil ni una renta del trabajo por grupo de edad y municipio que pueda relacionarse con EMAL. La API PxWeb consultada devolvió HTTP 403; se comprobó la descarga directa del PC-Axis, que tampoco proporciona el cruce municipal por edad.
- **Distinción conceptual:** la renta personal anual y la renta del trabajo de Eustat no equivalen a salario neto mensual. La renta personal puede incluir trabajo, actividades económicas, transferencias y capital. La renta del trabajo por persona tampoco representa necesariamente un salario neto de una persona asalariada. Estos datos se documentan como contexto y no se usan en las fórmulas principales.

## Demografía: población total de Udalmap

- **Responsable/publicación:** Udalmap, Gobierno Vasco.
- **Catálogo:** [Población total (hab.)](https://opendata.euskadi.eus/catalogo/-/indicadores-municipales-de-sostenibilidad-poblacion-total-hab/).
- **Fichero comprobado:** [CSV del indicador 162](https://opendata.euskadi.eus/contenidos/estadistica/udalmap_indicador_162/es_def/adjuntos/indicator.csv); HTTP 200, tamaño observado: 64.812 bytes.
- **Variables:** población total por municipio y año.
- **Cobertura:** Euskadi; el fichero incorpora datos municipales y agregados territoriales.
- **Periodo/frecuencia:** serie anual hasta 2025; actualización anual. El total autonómico publicado para 2025 es 2.218.210 habitantes.
- **Limitación:** no contiene en este indicador grupos de edad; la población se usará como contexto y no como sustituto de población joven.
- **Licencia:** CC BY 4.0.

## Relación de fuentes y reglas

EMAL aporta 73 códigos municipales únicos en la hoja anual de alquiler; los 73 están presentes en los ficheros de renta y población descargados. La unión se hará por código municipal oficial de cinco caracteres, almacenado como texto para conservar ceros iniciales. Se conservará también el nombre y la procedencia para auditoría.

El conjunto analítico de alquiler queda limitado a los municipios publicados por EMAL. No se repartirán rentas, ingresos ni población de un territorio o municipio entre otros. Los valores ausentes y la ruptura territorial de Galdakao/Usansolo quedarán marcados y excluidos de comparaciones incompatibles.

## Resultado de extracción y validación local

Los originales XLSX/CSV/JSON fueron descargados y almacenados sin transformación. Los descargadores registran URL, fecha UTC, estado HTTP, tamaño y SHA-256 en archivos laterales JSON; una ejecución repetida valida el hash y omite descargas innecesarias. El HTML municipal raspado se conserva intacto con esos metadatos. Tras normalizar, `scripts.extraccion.descargar_api_renta_udalmap` y `scripts.extraccion.scrapear_renta_udalmap` contrastan API/HTML con el CSV canónico.

El procesamiento real obtuvo 740 filas anuales de alquiler (2016–2025), 4.032 filas municipio-año de renta (2001–2023) y 6.300 filas municipio-año de población (2001–2025). La cobertura de Udalmap fue de 252 códigos municipales y la de alquiler, 73 códigos actuales. Los 73 códigos de alquiler están presentes en las dos fuentes Udalmap y tienen datos completos para la comparación de 2023; los nulos de los otros periodos se conservaron. Los detalles y ejemplos de nulos están en `datos/procesados/validacion_datos.json`.

## Fuentes no seleccionadas

Los portales comerciales de anuncios no se usarán como base principal: publican precios ofertados, no necesariamente contratos cerrados, y no se confirmó una API pública o permiso de scraping aplicable. La selección puede ampliarse si en otra fase se verifica acceso, licencia y condiciones de uso.
