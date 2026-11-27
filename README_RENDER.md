# CENTINELA IA 2.1.3 — paquete para Render

Este paquete parte de los módulos individuales extraídos del cuaderno original. Se conserva la interfaz y la lógica de la aplicación; los cambios de despliegue se limitan al arranque de Gradio para escuchar en `0.0.0.0` y utilizar el puerto `PORT` que proporciona Render.

## Archivos principales

- `app.py`: aplicación Gradio y arranque web configurado para Render.
- `evolucion_centinela.py`: gráficas y construcción de agenda.
- `avisos_centinela.py`: avisos y textos de privacidad.
- `voces_centinela.py`: voces Piper y gestión de modelos.
- `datos_demo_centinela.py`: datos de demostración.
- `centinela_audios_212/`: muestras de voz y avisos de audio incluidos.
- `requirements.txt`: dependencias Python.
- `Dockerfile`: imagen con Python y dependencias del sistema para audio.
- `render.yaml`: configuración inicial de Render.

## Publicación

1. Descomprime el ZIP.
2. Sube **todo el contenido de esta carpeta** a un repositorio de GitHub. No subas solo `app.py`.
3. En Render selecciona **New + > Blueprint** si deseas que lea `render.yaml`, o crea un **Web Service** conectado al repositorio y elige **Docker** como entorno.
4. Si creas el servicio manualmente, usa la raíz del repositorio como Root Directory y deja que Render construya el `Dockerfile`.
5. Inicia el despliegue y revisa los registros. Render asigna el dominio `onrender.com` cuando el servicio queda activo.

## Variables configuradas

- `PORT`: puerto web; Render lo proporciona. El paquete usa `10000` como valor local predeterminado.
- `APP_TIMEZONE`: zona horaria, configurada como `America/Mexico_City`.
- `CENTINELA_DB`: ruta de SQLite.
- `CENTINELA_MODELOS_VOZ`: carpeta para los modelos Piper descargados y verificados.
- `CENTINELA_INTERNAL_REMINDERS`: activa el ciclo interno de recordatorios.

Si habilitas la conversación avanzada con OpenAI, agrega `OPENAI_API_KEY` como **Secret** en Render. No escribas la clave dentro de `app.py`, `render.yaml` ni en GitHub.

## Persistencia: importante

La configuración incluida usa el plan gratuito para facilitar una primera demostración. El sistema de archivos del servicio gratuito es efímero: la base SQLite y los modelos descargados pueden perderse al reiniciar o desplegar de nuevo. El plan gratuito de Render no admite discos persistentes. Para conservar el historial SQLite entre reinicios, cambia a un plan que permita disco persistente, agrega un disco montado en `/var/data` y cambia:

`CENTINELA_DB=/var/data/centinela.sqlite3`

`CENTINELA_MODELOS_VOZ=/var/data/modelos_piper`

Alternativamente, habría que adaptar la aplicación para usar una base de datos administrada como PostgreSQL; esta versión utiliza SQLite y no está convertida a PostgreSQL.

## Recursos y límites

Whisper y Piper pueden descargar modelos y consumir memoria/CPU. En una instancia gratuita pequeña, el reconocimiento o la síntesis de voz pueden tardar, quedarse sin memoria o requerir una instancia con más recursos. La primera descarga de los modelos de voz necesita conexión a internet. La cámara depende del permiso del navegador y de que la conexión soporte la transmisión.

## Uso responsable

Esta aplicación es un prototipo de acompañamiento y demostración. No es un dispositivo médico, no diagnostica, no sustituye a profesionales y no debe utilizarse como sistema de emergencias. Para pruebas y presentaciones utiliza datos ficticios. Antes de usar información real de personas, se requiere una revisión de seguridad, privacidad, control de acceso, respaldo y cumplimiento legal.
