# Preparación de Kafka y HDFS

Las integraciones están implementadas y se verificaron en esta revisión contra los servicios reales configurados en el `.env` local (ignorado por Git). Se cargaron y recuperaron archivos mediante WebHDFS, y se ejecutó Kafka → MongoDB con eventos simulados. Las instrucciones siguientes permiten repetir el flujo; los servicios y parámetros deben seguir disponibles.

## Evidencia de ejecución real

- **WebHDFS:** 18 archivos originales y 10 procesados se subieron y verificaron por tamaño y SHA-256. El listado remoto devolvió 28 archivos y 9 directorios. El archivo `datos/recuperados/verificacion_salarios_juveniles_hdfs.csv` se recuperó desde HDFS y su SHA-256 coincidió con la fuente. Registro: `logs/hdfs.log`.
- **Kafka:** se creó el tópico aislado `reto_vivienda_iabd_user11`. Se publicaron dos eventos simulados en la partición 0 (offsets 0 y 1); el consumidor los persistió en MongoDB y confirmó los offsets. El grupo quedó comprometido en el offset siguiente 2. Ambos documentos están en `anuncios_stream` y los importes son `Decimal128`. Registro: `logs/kafka.log`.
- El flujo prueba la integración técnica, no la ingestión de anuncios reales. Los eventos simulados no se utilizan en los análisis estadísticos de alquiler.
- Los detalles estructurados se conservan en `resultados/tablas/verificacion_integraciones_bda.json`.

## Kafka

### Configuración

1. En un entorno nuevo, copie `.env.example` como `.env` únicamente si `.env` todavía no existe; configure `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, `KAFKA_SECURITY_PROTOCOL` y `KAFKA_GROUP_ID`. Si el broker usa SASL, configure mecanismo, usuario y contraseña; si usa TLS, configure el CA cuando corresponda. Ajuste también particiones y factor de replicación al cluster. No sobrescriba ni comparta un `.env` ya configurado.

   ```powershell
   Copy-Item ".env.example" ".env"
   ```
2. Para una demostración local de un único nodo KRaft, indique la ruta de su distribución Kafka y copie la plantilla del proyecto como configuración del broker. Ejecute los comandos desde la raíz del proyecto:

   ```powershell
   $KAFKA_HOME = "C:\ruta\real\de\kafka"
   Copy-Item ".\config\kafka\server.properties.example" "$KAFKA_HOME\config\server.properties" -Force
   ```

   La plantilla escucha únicamente en `localhost`, con un broker/controlador, un factor de replicación y un directorio de datos de ejemplo. No la use como configuración de producción ni sobrescriba una configuración existente sin revisarla.
3. Formatee el almacenamiento KRaft **solo al crear un cluster nuevo y vacío**. No vuelva a formatear el directorio de datos de un cluster existente. En una terminal PowerShell:

   ```powershell
   $KAFKA_HOME = "C:\ruta\real\de\kafka"
   $CLUSTER_ID = (& "$KAFKA_HOME\bin\windows\kafka-storage.bat" random-uuid).Trim()
   if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el identificador KRaft." }
   Push-Location $KAFKA_HOME
   & ".\bin\windows\kafka-storage.bat" format --standalone -t $CLUSTER_ID -c ".\config\server.properties"
   if ($LASTEXITCODE -ne 0) { Pop-Location; throw "No se pudo inicializar KRaft." }
   ```

4. Inicie el broker en una terminal separada y déjelo activo:

   ```powershell
   $KAFKA_HOME = "C:\ruta\real\de\kafka"
   Push-Location $KAFKA_HOME
   & ".\bin\windows\kafka-server-start.bat" ".\config\server.properties"
   ```

   Al detenerlo con `Ctrl+C`, ejecute `Pop-Location` en esa terminal.

### Demostración con los scripts

Cada bloque se puede copiar por separado. Ejecute primero la creación del tópico; después inicie el consumidor en una terminal y envíe el mensaje simulado desde otra.

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.kafka.crear_topico
```

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.kafka.consumidor_anuncios
```

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.kafka.productor_anuncios --municipality-code 20059 --municipality-name "Oñati" --monthly-rent-eur 600
```

El productor emite JSON con `is_simulated: true`; no es un anuncio real ni se incorpora a los indicadores oficiales. El consumidor valida el mensaje y lo guarda por `event_id` en `anuncios_stream`; confirma el offset solo después de persistirlo. Un reintento conserva un único documento para el mismo identificador. Los errores se registran en `logs/kafka.log`.

## HDFS/WebHDFS

Configure en `.env` `HDFS_URL`, `HDFS_USER` y `HDFS_BASE_PATH` para el servicio real. El cliente implementado usa autenticación WebHDFS simple mediante usuario. No incluye Kerberos ni otros mecanismos; si el cluster los exige, será necesario adaptar la autenticación antes de usarlo. No se incluyen credenciales.

Cada bloque incluye su propia selección del entorno Python:

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.hdfs.gestionar_hdfs init
```

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.hdfs.gestionar_hdfs upload --scope originales
```

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.hdfs.gestionar_hdfs upload --scope procesados
```

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.hdfs.gestionar_hdfs list
```

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.hdfs.gestionar_hdfs verify --local-file "datos/originales/alquiler/emal_alquiler_municipios_2016-2026T1.xlsx" --remote-relative-path "originales/alquiler/emal_alquiler_municipios_2016-2026T1.xlsx"
```

```powershell
$PY = "C:\Users\iker.bilbaoarrieta\AppData\Local\anaconda3\envs\IA\python.exe"
& $PY -m scripts.hdfs.gestionar_hdfs download --remote-relative-path "procesados/municipios_referencia.csv"
```

`upload` conserva la separación entre originales y procesados y verifica tamaño y SHA-256 de cada archivo. `download` también verifica el archivo recuperado; por defecto lo guarda bajo `datos/recuperados/`. `list` consulta el árbol remoto. Los resultados solo se podrán considerar almacenados en HDFS después de ejecutar estas comprobaciones contra el cluster configurado.
