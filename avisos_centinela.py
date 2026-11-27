"""Avisos y controles de privacidad de la demostración de CENTINELA IA."""
import base64
import html
import os
import voces_centinela as voces

VERSION = "2.1"

# El audio incluido lee estos mismos mensajes. Solo contiene texto general.
ALCANCE = ("CENTINELA organiza tu día y recuerda horarios. No da diagnósticos ni recetas. "
           "Los cambios de tratamiento corresponden a tu equipo médico.")
ACCESO = ("Cualquier persona con el enlace puede abrir ambos perfiles. Usa solo datos ficticios. "
          "La cámara y el micrófono son opcionales.")
TEXTO_AUDIO = (f"{ALCANCE} {ACCESO} Puedes probar la voz de ejemplo y, para mostrar la cámara, "
               "apuntar a un objeto. Puedes leer el aviso completo desde esta pantalla.")

SECCIONES = {
    "día": ("Tu registro del día", "Al guardar, la actividad queda en el historial del caso. "
            "Puedes dejar la nota en blanco. Si compartes Actividades realizadas, el cuidador podrá ver la fecha, la hora programada, tu respuesta y las notas que guardes."),
    "bienestar": ("Tú eliges qué contar", "Puedes omitir estas preguntas. Si guardas tus respuestas, se registran tu descanso, energía y la nota que escribas. "
                  "Si compartes Bienestar, el cuidador verá un resumen y podrá leer tus valores y las notas de los días que consulte."),
    "dictado": ("Antes de dictar", "Tu audio se envía a Colab para pasarlo a texto. Comprueba lo que se entendió antes de guardar. También puedes responder tocando una opción o escribiendo."),
    "evolución propia": ("Cómo leer la estimación", "El modelo estima la probabilidad de registrar una confirmación a partir de horarios anteriores. No evalúa tu salud ni comprueba que hayas tomado un medicamento."),
    "hablar": ("Antes de hablar", "El audio que grabes o subas se envía a Colab para pasarlo a texto. El asistente puede entenderte mal. "
               "Puedes escribir tu mensaje o usar la voz de ejemplo sin encender el micrófono."),
    "medicamentos": ("Qué significa tu confirmación", "«Ya lo tomé» guarda tu declaración. «Por confirmar» significa que falta el registro. "
                     "Si tienes dudas sobre una dosis o un horario, consulta al profesional que te lo indicó."),
    "actividades": ("Tus preferencias", "Las actividades favoritas y las notas que guardes se ven también en el perfil del cuidador. Para la demostración usa ejemplos inventados."),
    "lugares": ("Antes de buscar", "Con Google Places, al pulsar Buscar se envían a Google la actividad y la zona. Sin ese servicio, se envían al abrir el enlace de Google Maps. Usa una colonia o ciudad y evita escribir tu domicilio."),
    "cámara": ("Tú decides cuándo compartir", "Se envían imágenes sin audio al servidor. Cualquiera con el enlace puede verlas desde el perfil del cuidador. "
               "Para el coloquio, apunta a un objeto y evita captar al público. Para apagarla, pulsa «Dejar de compartir». También se apaga al cambiar de perfil."),
    "ayuda": ("Pedir apoyo", "Al abrir WhatsApp se le pasan el teléfono del contacto y un texto preparado. Tú eliges si lo envías. "
              "CENTINELA no llama ni alerta automáticamente. En una emergencia en México, llama directamente al 911."),
    "compartida": ("Cómo leer las gráficas", "Elige una rutina para ver sus resultados y el bienestar declarado en los días que se marcó como realizada. "
                   "La hora de la actividad es la de la agenda. «Sin registro» indica que falta una respuesta. «Pendiente hoy» incluye rutinas sin hora o previstas para más tarde. "
                   "Los medicamentos se muestran siempre por su propio horario. Una confirmación recoge lo que declaró la persona."),
    "resumen": ("Qué muestra el resumen", "Aquí siguen visibles los horarios, las confirmaciones de hoy y los movimientos recientes, aunque una gráfica esté oculta. "
                "Si algo te preocupa, habla con la persona. Un horario pendiente solo indica que falta una confirmación."),
    "plan": ("Horarios que registra el cuidador", "Usa medicamentos ficticios en el coloquio. Al copiar un plan, usa las indicaciones vigentes del profesional tratante. "
             "Desactivar un medicamento aquí apaga sus recordatorios. Los cambios de tratamiento corresponden a quien lo prescribe."),
    "gustos": ("Preferencias compartidas", "La persona acompañada puede ver las actividades que añadas. Pregúntale antes de escribir notas sobre movilidad, salud o apoyo."),
    "familia": ("Datos de familiares y cuidadores", "El nombre, la relación y el teléfono que guardes estarán disponibles en esta demostración. "
                "Usa contactos inventados. Antes de registrar a alguien en un piloto, infórmale para qué se usarán sus datos."),
    "remota": ("Antes de abrir la cámara", "Mira las imágenes solo si la persona ha aceptado compartirlas. Evita hacer capturas o difundirlas. "
               "La señal puede interrumpirse. CENTINELA no detecta caídas ni ofrece vigilancia continua."),
}


def nota(clave):
    titulo, cuerpo = SECCIONES[clave]
    return (f'<aside class="aviso-contexto" aria-label="{html.escape(titulo)}">'
            f'<strong>{html.escape(titulo)}</strong><p>{html.escape(cuerpo)}</p></aside>')


def datos_organizacion():
    return {k: os.environ.get("CENTINELA_AVISO_" + k, "").strip() for k in
            ("RESPONSABLE", "DOMICILIO", "CONTACTO", "CONSERVACION", "FUNDAMENTO", "UNIDAD")}


def aviso_html(voz=voces.VOZ_INICIAL, ritmo=voces.RITMO_INICIAL):
    org = datos_organizacion()
    campos = [("RESPONSABLE", "Responsable"), ("DOMICILIO", "Domicilio institucional"),
              ("CONTACTO", "Canal para ejercer tus derechos"), ("FUNDAMENTO", "Fundamento institucional"),
              ("UNIDAD", "Unidad de Transparencia y domicilio")]
    filas = "".join(f"<dt>{nombre}</dt><dd>{html.escape(org[k])}</dd>" for k, nombre in campos if org[k])
    ficha = f"<dl>{filas}</dl>" if filas else ""
    contacto = (f"Dirige tu solicitud a {org['CONTACTO']}." if org["CONTACTO"] else
                "Durante el coloquio, dirígete a la persona que presenta y solicita el canal institucional de privacidad.")
    ficha_breve = ""
    if org["RESPONSABLE"]:
        identificacion = " · ".join(org[k] for k in ("RESPONSABLE", "DOMICILIO", "CONTACTO") if org[k])
        ficha_breve = f"<p><strong>Responsable del tratamiento.</strong> {html.escape(identificacion)}</p>"
    if not all(org[k] for k in ("RESPONSABLE", "DOMICILIO", "CONTACTO")):
        ficha += "<p>Esta edición está preparada para ejemplos ficticios. Queda por completar la identificación o el contacto institucional antes de recibir datos de personas reales.</p>"
    drive = os.getenv("CENTINELA_AVISO_DRIVE") == "1"
    ubicacion = ("En esta ejecución se eligió guardar el historial en Google Drive. El archivo permanece allí hasta que la persona responsable lo gestione, incluida su papelera."
                 if drive else "En esta ejecución el historial se guarda en la carpeta del entorno. En un entorno temporal de Colab se pierde al eliminar ese entorno, salvo que se haya copiado.")
    conservacion = (f"El criterio de conservación declarado por la organización es el siguiente. {org['CONSERVACION']}"
                    if org["CONSERVACION"] else "No se ha fijado un plazo institucional para datos de personas reales. La aplicación no borra la base de ensayo al salir.")
    secciones = [
        ("Para qué sirve y qué datos se usan", "El equipo que organiza la presentación muestra un caso ficticio. La agenda emplea nombre de pila, zona general, rutinas y contactos. El diario usa descanso, energía, notas, horarios de medicamentos y confirmaciones. Los datos identificables que revelen salud son sensibles. El cuidador puede añadir preferencias y contactos, y quedan movimientos de sus acciones en el historial."),
        ("Quién puede ver el caso", "El enlace es de acceso libre. Cualquiera puede ver y modificar el caso entrando como persona acompañada o cuidador. Las categorías activadas en Mis permisos y preferencias controlan las gráficas y sus detalles, incluidas las notas de las fechas consultadas. Al guardar cambios, se aplican la próxima vez que se abre o actualiza Evolución compartida. El resumen diario, el plan, los favoritos y el directorio siguen disponibles. La autorización de la cámara es independiente."),
        ("Voz, chat y cámara", "Gradio comunica el navegador con el entorno de Colab. Whisper transcribe allí los audios. Puedes escribir o usar la grabación incluida. Las cuatro voces se generan en Colab. El cuaderno descarga sus modelos y guarda la voz y el ritmo elegidos con el perfil. Las muestras y el aviso son grabaciones sintéticas incluidas. En Hablar puedes permitir por separado que OpenAI reciba una consulta y hasta ocho mensajes previos, o elegir la voz de Google para el chat. Si eliges Google, recibirá el texto de las respuestas. Guardar una de las cuatro voces vuelve a activar la lectura en Colab para el chat. Ambas opciones empiezan desactivadas en cada visita. La cámara envía fotogramas sin audio si decides compartirlos. El servidor mantiene la imagen reciente y la retira al detener el envío. No crea un archivo de video. La plataforma puede procesar archivos temporales."),
        ("Mapas, mensajería y proyección", "Al usar Google Places o abrir una búsqueda en Maps, Google recibe la actividad y la zona. Al abrir WhatsApp se le pasan el número y el texto preparado. El envío del mensaje es manual. Lo que proyectes o reproduzcas en el salón será visible o audible para el público. Usa un objeto para la cámara y la voz de ejemplo para la presentación."),
        ("Dónde se guarda y durante cuánto tiempo", f"{ubicacion} {conservacion} Cambiar de perfil corta la cámara y cierra el chat de esa visita en pantalla. Los datos guardados siguen en el historial. Mientras funciona, Gradio revisa su caché cada hora para retirar archivos temporales con más de una hora de antigüedad. Los servicios externos aplican sus propias políticas a los datos que reciben."),
        ("Tus decisiones y tus derechos", f"Tanto la persona acompañada como el cuidador pueden solicitar acceso, rectificación, cancelación u oposición (derechos ARCO), o pedir que se limite el uso de sus datos y revocar su consentimiento cuando proceda. {contacto} Indica qué derecho quieres ejercer y a qué registro te refieres. El responsable te explicará cómo acreditar tu identidad por un canal privado. Evita escribir tu solicitud o identificación en el chat público de la demo."),
        ("Cómo retirar un permiso", "Puedes omitir el diario, desmarcar categorías y guardar tus preferencias, escribir sin micrófono, desmarcar los servicios opcionales para tus próximos mensajes o pulsar Dejar de compartir. La persona acompañada decide sobre su información. Entrar como cuidador no otorga representación legal. Retirar un permiso detiene el uso futuro correspondiente. Para solicitar la cancelación de registros previos, utiliza el canal de privacidad."),
        ("Cambios al aviso", f"Esta versión del aviso corresponde a CENTINELA IA {VERSION}. Los cambios se publican en este mismo apartado antes de usar las funciones afectadas."),
    ]
    contenido = "".join(f"<h3>{html.escape(t)}</h3><p>{html.escape(p)}</p>" for t, p in secciones)
    lectura = voces.AUDIOS / f"aviso_{voz}.mp3"
    audio = base64.b64encode(lectura.read_bytes()).decode("ascii")
    return f'''<section class="aviso-principal" aria-label="Privacidad de la demostración">
      <div class="aviso-intro"><p><strong>Alcance de CENTINELA.</strong> {html.escape(ALCANCE)}</p>
      <p><strong>Privacidad del coloquio.</strong> {html.escape(ACCESO)}</p>{ficha_breve}</div>
      <div class="aviso-acciones">
        <button type="button" data-lectura aria-expanded="false" aria-controls="aviso-integral">Leer aviso de privacidad</button>
        <button type="button" data-voz aria-expanded="false" aria-controls="aviso-reproductor">Escuchar aviso breve</button>
      </div>
      <div id="aviso-reproductor" hidden><audio controls preload="none" data-ritmo="{voces.RITMOS[ritmo][1]}" aria-label="Lectura del aviso breve" src="data:audio/mpeg;base64,{audio}"></audio></div>
      <article id="aviso-integral" hidden aria-labelledby="titulo-aviso">
        <h2 id="titulo-aviso">Aviso de privacidad de la demostración</h2>
        <h3>Responsable y contacto</h3><div>{ficha}</div>
        {contenido}
        <h3>Referencias para México</h3><ul>
        <li><a href="https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf" target="_blank" rel="noopener noreferrer">Ley federal para datos en posesión de particulares</a></li>
        <li><a href="https://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf" target="_blank" rel="noopener noreferrer">Ley general para datos en posesión de sujetos obligados</a></li>
        </ul></article></section>'''


LECTOR_JS = """
element.onclick = async (event) => {
    const button = event.target.closest("button[data-lectura], button[data-voz]");
    if (!button || !element.contains(button)) return;
    const panel = element.querySelector("#" + button.getAttribute("aria-controls"));
    panel.hidden = !panel.hidden;
    button.setAttribute("aria-expanded", String(!panel.hidden));
    if (button.hasAttribute("data-lectura")) {
        button.textContent = panel.hidden ? "Leer aviso de privacidad" : "Cerrar aviso de privacidad";
        return;
    }
    const audio = panel.querySelector("audio");
    button.textContent = panel.hidden ? "Escuchar aviso breve" : "Cerrar lectura del aviso";
    if (panel.hidden) { audio.pause(); return; }
    audio.playbackRate = Number(audio.dataset.ritmo) || 1;
    try { await audio.play(); } catch { audio.focus(); }
};
"""

