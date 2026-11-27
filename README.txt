CENTINELA IA 2.1.3 - ARCHIVOS INDIVIDUALES EXTRAIDOS DEL NOTEBOOK ORIGINAL

Contenido:
- app.py
- avisos_centinela.py
- evolucion_centinela.py
- datos_demo_centinela.py
- voces_centinela.py
- requirements.txt
- voz_ejemplo.mp3
- centinela_audios_212/ (audios incluidos en el notebook original)

IMPORTANTE:
1. Estos cinco módulos Python se extrajeron de las secciones %%writefile del archivo original.
   No se reescribió la lógica interna de esos módulos.
2. requirements.txt reúne las dependencias declaradas en la celda de instalación original.
3. La aplicación usa SQLite local. En servicios gratuitos con disco efímero, el historial puede
   perderse al reiniciar o redeplegar.
4. app.py tiene una función launch() configurada originalmente para la ejecución del notebook.
   Para un servidor como Render será necesario adaptar el inicio para escuchar en 0.0.0.0 y el
   puerto PORT asignado por el proveedor. No se incluye una configuración de servidor no probada.
5. El notebook original contiene también las celdas de configuración institucional, selección
   del escenario ficticio y lanzamiento desde Colab. Esos pasos no forman parte de los módulos.
6. Utiliza únicamente datos ficticios para pruebas. No es un dispositivo médico ni un sistema
   de emergencias.

Para probar localmente, instala dependencias con:
    pip install -r requirements.txt

Después ejecuta:
    python app.py

Esta prueba puede requerir recursos adicionales para descargar y ejecutar los modelos de voz.
