"""Voces de presentación. Piper sintetiza en el mismo entorno que ejecuta CENTINELA."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
import threading
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import requests
try:
    import onnxruntime as ort
except ImportError:
    ort = None
else:
    ort.disable_telemetry_events()


@dataclass(frozen=True)
class Voz:
    nombre: str
    pais: str
    modelo: str
    hablante: int | None = None

    @property
    def etiqueta(self):
        return f"{self.nombre} · {self.pais}"


VOCES = {
    "sol": Voz("Sol", "México", "es_MX-claude-high"),
    "rio": Voz("Río", "México", "es_MX-ald-medium"),
    "ines": Voz("Inés", "España", "es_ES-sharvard-medium", 1),
    "leo": Voz("Leo", "España", "es_ES-sharvard-medium", 0),
}
RITMOS = {"pausado": ("Pausado", 0.82), "habitual": ("Habitual", 1.0), "agil": ("Ágil", 1.14)}
VOZ_INICIAL, RITMO_INICIAL = "sol", "habitual"
FRASE_MUESTRA = "Hola. ¿Cómo estás hoy? Cuando quieras, revisamos tu agenda."
AUDIOS = Path(__file__).resolve().with_name("centinela_audios_212")

REVISION = "375a0fe641dea077c2a47b4e9a056d6da521eed3"
MODELOS = {
    "es_MX-claude-high": ("3ef40a71ea63852cd8ab7e6fa7d2ecdcfa67a0b47c9c48e3f10e02ee02083ea0",
                         "1afc81f703c0e4cb3b4d7c0dca096b8b54a98806807f0170cf5eb5557723c12d"),
    "es_MX-ald-medium": ("019b3803293c93e34a206dd2e53a3889209a514e786fd7144f7b70196c579b63",
                        "efab736e62e5321dd5d063d1b46e63c59ce655419816355b81d025c1a8d6b03c"),
    "es_ES-sharvard-medium": ("40febfb1679c69a4505ff311dc136e121e3419a13a290ef264fdf43ddedd0fb1",
                             "7438c9b699c72b0c3388dae1b68d3f364dc66a2150fe554a1c11f03372957b2c"),
}
BLOQUEO_MOTOR = threading.Lock()


def carpeta_modelos():
    ruta = os.getenv("CENTINELA_MODELOS_VOZ")
    return Path(ruta).expanduser() if ruta else Path.home() / ".cache" / "centinela" / "piper" / REVISION


def preparar_modelo(modelo):
    """Reutiliza archivos verificados. Una descarga interrumpida no reemplaza una copia válida."""
    carpeta = carpeta_modelos()
    carpeta.mkdir(parents=True, exist_ok=True)
    idioma, nombre, calidad = modelo.split("-")
    base = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/es/{idioma}/{nombre}/{calidad}"
    for extension, esperado in zip((".onnx", ".onnx.json"), MODELOS[modelo]):
        destino = carpeta / (modelo + extension)
        if destino.is_file():
            huella = hashlib.sha256()
            with destino.open("rb") as existente:
                for bloque in iter(lambda: existente.read(1024 * 1024), b""):
                    huella.update(bloque)
            if huella.hexdigest() == esperado:
                continue
        with tempfile.NamedTemporaryFile(dir=carpeta, suffix=".parcial", delete=False) as archivo:
            temporal = Path(archivo.name)
        try:
            with requests.get(f"{base}/{destino.name}", params={"download": "true"},
                              stream=True, timeout=(8, 45)) as respuesta:
                respuesta.raise_for_status()
                huella = hashlib.sha256()
                with temporal.open("wb") as archivo:
                    for bloque in respuesta.iter_content(1024 * 1024):
                        archivo.write(bloque)
                        huella.update(bloque)
            if huella.hexdigest() != esperado:
                raise ValueError("El archivo de voz recibido está incompleto o ha cambiado.")
            temporal.replace(destino)
        finally:
            temporal.unlink(missing_ok=True)


@lru_cache(maxsize=2)
def _motor(modelo, carpeta):
    if ort is None:
        raise ImportError("Falta ONNX Runtime para las voces locales.")
    from piper import PiperVoice
    from piper.config import PiperConfig

    ruta = carpeta / (modelo + ".onnx")
    with ruta.with_suffix(".onnx.json").open(encoding="utf8") as archivo:
        datos = json.load(archivo)
    # La ficha original de Ald usa el nombre largo del enumerado de Piper 1.0.
    if datos.get("phoneme_type") == "PhonemeType.ESPEAK":
        datos["phoneme_type"] = "espeak"
    configuracion = PiperConfig.from_dict(datos)
    opciones = ort.SessionOptions()
    opciones.intra_op_num_threads = 2
    opciones.inter_op_num_threads = 1
    opciones.add_session_config_entry("session.intra_op.allow_spinning", "0")
    sesion = ort.InferenceSession(str(ruta), sess_options=opciones, providers=["CPUExecutionProvider"])
    return PiperVoice(sesion, configuracion)


_UNIDADES = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince "
             "dieciséis diecisiete dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro "
             "veinticinco veintiséis veintisiete veintiocho veintinueve").split()
_HORA = re.compile(r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])"
                   r"( de la (?:mañana|tarde|noche|madrugada|medianoche)| del mediodía)?", re.IGNORECASE)


def _hora_en_palabras(coincidencia):
    hora, minuto = int(coincidencia[1]), int(coincidencia[2])
    periodo = coincidencia[3]
    if not periodo:
        if hora < 6:
            periodo = " de la madrugada" if hora else " de la noche"
        elif hora < 12:
            periodo = " de la mañana"
        elif hora < 19:
            periodo = " del mediodía" if hora == 12 and minuto == 0 else " de la tarde"
        else:
            periodo = " de la noche"
    h = hora % 12 or 12
    horas = "una" if h == 1 else _UNIDADES[h]
    if not minuto:
        return horas + periodo
    if minuto in (15, 30):
        minutos = "cuarto" if minuto == 15 else "media"
    elif minuto < 30:
        minutos = _UNIDADES[minuto]
    else:
        minutos = {3: "treinta", 4: "cuarenta", 5: "cincuenta"}[minuto // 10]
        if minuto % 10:
            minutos += " y " + _UNIDADES[minuto % 10]
    return horas + " y " + minutos + periodo


def para_leer(texto):
    texto = _HORA.sub(_hora_en_palabras, texto)
    texto = re.sub(r"\bson las una\b", "es la una", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\blas una\b", "la una", texto, flags=re.IGNORECASE)
    return texto.replace("**", "").replace(" · ", ", ").strip()


def sintetizar(texto, voz, ritmo):
    """Genera un WAV sin tocar disco ni transmitir el contenido del mensaje."""
    from piper import SynthesisConfig

    seleccion = VOCES[voz]
    opciones = SynthesisConfig(speaker_id=seleccion.hablante, length_scale=1 / RITMOS[ritmo][1],
                               noise_scale=0.62, noise_w_scale=0.72, volume=0.90)
    salida = io.BytesIO()
    # El fonemizador y las sesiones de inferencia se comparten entre pestañas.
    with BLOQUEO_MOTOR:
        motor = _motor(seleccion.modelo, carpeta_modelos())
        with wave.open(salida, "wb") as wav:
            frecuencia = motor.config.sample_rate
            wav.setparams((1, 2, frecuencia, 0, "NONE", "not compressed"))
            pausa = b"\x00\x00" * round(frecuencia * 0.18 / RITMOS[ritmo][1])
            for fragmento in motor.synthesize(para_leer(texto), syn_config=opciones):
                if wav.tell():
                    wav.writeframesraw(pausa)
                wav.writeframesraw(fragmento.audio_int16_bytes)
            if not wav.tell():
                raise ValueError("La voz no produjo audio.")
    return salida.getvalue()

