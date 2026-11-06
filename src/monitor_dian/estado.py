import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .clasificador import Resultado

HORAS_ENTRE_AVISOS_DE_ERROR = 24
SEGUNDOS_BLOQUEO_VENCIDO = 3600


class YaEnEjecucion(Exception):
    pass


@dataclass
class Estado:
    pausado: bool = False
    errores_seguidos: int = 0
    ultimo_aviso_error: str | None = None
    ultima_consulta: str | None = None
    ultimo_resultado: str | None = None


def cargar(ruta: Path) -> Estado:
    if not ruta.exists():
        return Estado()
    return Estado(**json.loads(ruta.read_text(encoding="utf-8")))


def guardar(ruta: Path, estado: Estado) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(asdict(estado), indent=2), encoding="utf-8")
    temporal.replace(ruta)


def agregar_historial(ruta: Path, ahora: datetime, consulta) -> None:
    """Solo guarda datos de la búsqueda: nunca valores de `.env`."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    registro = {
        "hora": ahora.isoformat(timespec="seconds"),
        "modalidad": consulta.busqueda.modalidad,
        "servicio": consulta.busqueda.servicio,
        "resultado": consulta.resultado.value,
        "tramites": consulta.tramites,
        "detalle": consulta.detalle,
    }
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


def es_bloqueo(resultado: Resultado, detalle: str) -> bool:
    return resultado is Resultado.ERROR_RED and ("HTTP 403" in detalle or "HTTP 429" in detalle)


def aplicar_resultado(
    estado: Estado,
    resultado: Resultado,
    detalle: str,
    ahora: datetime,
    errores_para_avisar: int,
) -> str | None:
    """Actualiza el estado y devuelve el aviso de error que corresponda enviar."""
    estado.ultima_consulta = ahora.isoformat(timespec="seconds")
    estado.ultimo_resultado = resultado.value

    if resultado in (Resultado.SIN_SERVICIO, Resultado.DISPONIBLE):
        estado.errores_seguidos = 0
        estado.ultimo_aviso_error = None
        estado.pausado = resultado is Resultado.DISPONIBLE
        return None

    estado.errores_seguidos += 1
    if es_bloqueo(resultado, detalle):
        estado.pausado = True
        return f"El sitio rechazó el acceso ({detalle}). El monitor se pausó."

    desconocida = resultado is Resultado.RESPUESTA_DESCONOCIDA
    if not desconocida and estado.errores_seguidos < errores_para_avisar:
        return None
    if estado.ultimo_aviso_error:
        anterior = datetime.fromisoformat(estado.ultimo_aviso_error)
        if ahora - anterior < timedelta(hours=HORAS_ENTRE_AVISOS_DE_ERROR):
            return None
    estado.ultimo_aviso_error = ahora.isoformat(timespec="seconds")
    if desconocida:
        return f"El sitio dio una respuesta desconocida ({detalle}). Revise la captura."
    return f"El monitor no está funcionando: {estado.errores_seguidos} errores seguidos."


def dentro_de_pausa_horaria(ahora: datetime, desde: str, hasta: str) -> bool:
    hora = ahora.strftime("%H:%M")
    if desde <= hasta:
        return desde <= hora < hasta
    return hora >= desde or hora < hasta


@contextmanager
def bloqueo(ruta: Path):
    """Impide dos ejecuciones simultáneas. Un bloqueo viejo se considera abandonado."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists() and time.time() - ruta.stat().st_mtime > SEGUNDOS_BLOQUEO_VENCIDO:
        ruta.unlink(missing_ok=True)
    try:
        descriptor = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise YaEnEjecucion from error
    os.close(descriptor)
    try:
        yield
    finally:
        ruta.unlink(missing_ok=True)
