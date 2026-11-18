# Metodología

## Preparación

Los originales se preservan sin cambios. Los datos procesados se normalizan a filas con código municipal textual de cinco caracteres, nombre, periodo, valor y unidad. Las distintas geografías, ausencias, notas de provisionalidad y fechas de referencia de cada fuente se mantienen explícitas.

La hoja municipal EMAL (T2.1, T2.2, T2.3) se convierte de ancho a largo y se une por código, variante geográfica y año. Las hojas se comprobaron con idénticas claves. Los CSV Udalmap se leen como campos separados por punto y coma, codificación cp1252 y separadores decimales españoles. Los agregados de territorio y comarca se excluyen al exigir códigos de municipio de cinco dígitos. Los códigos permanecen como texto para conservar ceros iniciales.

La renta del CSV normalizado se contrasta con dos extracciones independientes del indicador 61: el endpoint REST documentado y la tabla HTML municipal raspada. La API omite el registro de Usansolo de 2023 porque no tiene valor; se conserva como nulo en el conjunto canónico y no se imputa. Ambas comprobaciones se guardan aparte y no duplican datos en MongoDB.

No se combinan automáticamente cifras de Galdakao antes y después de la segregación de Usansolo. El análisis solo usa las geografías y periodos compatibles que superan las validaciones.

El portal estadístico del Observatorio ofrece tablas interactivas y una respuesta JSON obtenida mediante un endpoint utilizado por la propia web. El descargador identifica los filtros desde las fichas oficiales, conserva intactas las respuestas y valida valores de los indicadores 31, 32 y 49. El portal y el PDF coinciden en los valores comprobados de salario 2024, coste de alquiler 2024 y renta personal 2023. La aplicación tiene datos del indicador 32 para 2024, pero el fichero normalizado y MongoDB conservan la edición PDF solicitada; esa renta personal sigue siendo contextual y no es salario. La exportación Excel existe en la interfaz, aunque la descarga automatizada ensayada devolvió un libro sin datos. Al no ser un endpoint JSON documentado, la respuesta del portal es un contraste y no sustituye al PDF como instantánea de referencia.

## Ingreso y comparabilidad

El análisis principal usa el salario mensual neto medio de personas asalariadas de 18–34 años publicado por el Observatorio Vasco de la Juventud (indicador 31), con pagas extraordinarias prorrateadas. En 2024 hay salarios totales por territorio histórico, y grupos de edad/sexo a nivel Euskadi; no existe en el PDF un cruce de edad × territorio ni salarios municipales.

Cada municipio se relaciona con el salario de Álava, Bizkaia o Gipuzkoa mediante el código territorial oficial (`01`, `48` o `20`). Es un promedio territorial aplicado a la comparación municipal, no una observación salarial municipal. Los grupos de edad y sexo permanecen en el nivel Euskadi y no se cruzan artificialmente con los territorios.

La renta personal disponible adulta de Udalmap (18+) se conserva como contexto y en el análisis complementario de 2023; no es salario. El indicador 32 del Observatorio/Eustat, renta personal anual de personas de 25–29 años, también permanece separado y no se convierte en salario mensual. Eustat publica renta personal y renta del trabajo por edad para Euskadi, y rentas por territorio/municipio en tablas sin el cruce de edad identificado en esta investigación. Ninguna de esas magnitudes equivale a salario neto juvenil.

## Comparación juvenil principal para 2024

Se unen por código municipal y año el alquiler EMAL de 2024, la población municipal Udalmap de 2024 y el salario neto territorial del indicador 31 de 2024. Las tablas cubren 72 municipios: EMAL contiene 73 registros geográficos actuales, pero Mutriku (`20056`) tiene la renta mensual nula y se excluye sin imputación. Los municipios pequeños sin dato EMAL tampoco se extrapolan.

- Alquiler mensual medio por contrato (EUR): EMAL.
- Salario neto mensual juvenil 18–34 (EUR): indicador 31 del Observatorio, código de territorio histórico.
- Porcentaje del salario destinado al alquiler: `alquiler_mensual / salario_neto_mensual * 100`.
- Dinero restante tras alquiler: `salario_neto_mensual - alquiler_mensual`.
- Máximo recomendado con esfuerzo de referencia del 30 %: `salario_neto_mensual * 0.30`.
- Diferencia entre alquiler real y máximo de referencia: `alquiler_mensual - alquiler_maximo_recomendado`.
- Población: total municipal Udalmap, usada solo como contexto.

El umbral del 30 % es una referencia analítica, no una garantía de emancipación ni una regla oficial. Un remanente positivo no prueba que el alquiler sea asequible: no se descuentan suministros, alimentación, transporte, fianza, gastos de mudanza ni otras necesidades. Los valores comparan medias, no hogares ni sueldos individuales.

Para el contraste territorial, el alquiler medio EMAL se pondera por número de fianzas en los municipios publicados. Se calcula `alquiler_territorial_ponderado / salario_territorial * 100` y se compara con el indicador 49. La cobertura municipal publicada por EMAL no necesariamente coincide con la cobertura completa empleada por el Observatorio; además, las rentas históricas pueden actualizarse por IRAV y marcarse provisionales.

Para edades se comparan solo los grupos coincidentes en las tablas del Observatorio: 18–29 y 30–34 a nivel Euskadi. No se asignan estos salarios autonómicos a municipios. El indicador 49 ofrece otros grupos, como 18–24 y 25–29, pero el indicador 31 no publica sus salarios correspondientes con esa misma segmentación, por lo que no se genera ese cruce.

## Indicadores adultos complementarios para 2023

Se conserva el cálculo anterior con el último año común disponible al construir la serie: alquiler EMAL, renta personal disponible adulta Udalmap y población. La agregación MongoDB combina alquiler, renta y población por código municipal y año. Este resultado es socioeconómico y no responde por sí mismo a la pregunta sobre salarios juveniles.

- Alquiler mensual medio por contrato (EUR): EMAL `renta mensual media`.
- Precio mensual por m² construido (EUR/m²): EMAL.
- Renta personal disponible anual media (EUR/persona adulta): Udalmap, 18+.
- Renta disponible mensual aproximada: `renta disponible anual / 12`.
- Alquiler como porcentaje de la renta disponible mensual: `alquiler mensual / renta disponible mensual * 100`.
- Renta disponible mensual restante tras alquiler: `renta disponible mensual - alquiler mensual`.
- Coste anual del alquiler: `alquiler mensual * 12`.
- Unidades de renta mensual necesarias para cubrir un año de alquiler: `coste anual del alquiler / renta disponible mensual`.

La renta disponible incluye distintas fuentes de ingreso y descuenta impuestos/retenciones; no es salario bruto ni neto. La estimación no descuenta suministros, alimentación, transporte, impuestos adicionales ni otros gastos y supone que una persona paga el contrato completo. Por eso el porcentaje y el remanente son indicadores comparativos, no una prueba de asequibilidad individual. EMAL advierte que rentas de años anteriores pueden estar actualizadas según IRAV y ser provisionales.

No se rellenan valores nulos ni se derivan valores municipales a partir de agregados. El PDF original se verifica por SHA-256; `pypdf` localiza los indicadores por su título y extrae las tablas, verificando los periodos y varios valores oficiales conocidos. La normalización comprueba que las celdas están completas.

Durante la carga PyMongo los salarios y las referencias monetarias se almacenan como `Decimal128`; los registros incluyen fuente, URL, hash y página. Los índices únicos y controles de dimensiones previenen duplicados. Las agregaciones de MongoDB efectúan los `$lookup` por códigos territoriales y años y calculan los indicadores juveniles; la población se enlaza por código municipal/año. Los informes y gráficos se regeneran desde dichas agregaciones.
