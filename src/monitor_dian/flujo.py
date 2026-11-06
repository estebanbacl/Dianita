import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Browser, Error, Page, Response
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .clasificador import (
    TEXTO_MODAL_SIN_SERVICIO,
    Resultado,
    clasificar,
    decodificar_respuesta,
    es_clasificable,
    nombres_tramites,
)

URL_SITIO = "https://agendamiento.dian.gov.co/"
RUTA_VALIDADOR = "/Player.aspx/ValidadorValidar"


@dataclass(frozen=True)
class Busqueda:
    persona: str
    modalidad: str
    servicio: str


@dataclass
class ResultadoConsulta:
    busqueda: Busqueda
    resultado: Resultado
    tramites: list[str] = field(default_factory=list)
    detalle: str = ""
    captura: Path | None = None


class _ErrorHttp(Exception):
    pass


def consultar(
    navegador: Browser, busqueda: Busqueda, tiempo_maximo_s: float, dir_capturas: Path
) -> ResultadoConsulta:
    """Recorre el formulario hasta el servicio, con un contexto de navegador nuevo."""
    contexto = navegador.new_context()
    pagina = contexto.new_page()
    pagina.set_default_timeout(tiempo_maximo_s * 1000)
    respuestas: list[Response] = []
    pagina.on(
        "response", lambda r: respuestas.append(r) if RUTA_VALIDADOR in r.url else None
    )
    try:
        consulta = _recorrer(pagina, busqueda, respuestas, tiempo_maximo_s)
        if consulta.resultado is Resultado.RESPUESTA_DESCONOCIDA:
            consulta.captura = _capturar(pagina, dir_capturas)
        return consulta
    except _ErrorHttp as error:
        return ResultadoConsulta(busqueda, Resultado.ERROR_RED, detalle=str(error))
    except PlaywrightTimeoutError as error:
        return ResultadoConsulta(
            busqueda,
            Resultado.ERROR_FLUJO,
            detalle=f"{error.message.splitlines()[0]} {_servicios_visibles(pagina)}",
            captura=_capturar(pagina, dir_capturas),
        )
    except Error as error:
        return ResultadoConsulta(
            busqueda, Resultado.ERROR_RED, detalle=error.message.splitlines()[0]
        )
    finally:
        contexto.close()


def abrir_hasta_modalidad(pagina: Page, busqueda: Busqueda) -> None:
    documento = pagina.goto(URL_SITIO)
    if documento is not None and documento.status != 200:
        raise _ErrorHttp(f"HTTP {documento.status} al abrir el sitio")

    pulsar_texto(pagina, "Agendar cita")
    esperar_carga(pagina)
    pulsar_texto(pagina, busqueda.persona)
    esperar_carga(pagina)
    pulsar_texto(pagina, busqueda.modalidad)
    esperar_carga(pagina)


def _recorrer(
    pagina: Page,
    busqueda: Busqueda,
    respuestas: list[Response],
    tiempo_maximo_s: float,
) -> ResultadoConsulta:
    abrir_hasta_modalidad(pagina, busqueda)

    marca = len(respuestas)
    pulsar_texto(pagina, busqueda.servicio)
    datos = _esperar_respuesta_clasificable(pagina, respuestas, marca, tiempo_maximo_s)

    modal = pagina.get_by_text(TEXTO_MODAL_SIN_SERVICIO).first
    if datos.get("Encontrado") is False:
        try:
            modal.wait_for(state="visible")
        except PlaywrightTimeoutError:
            pass
    resultado = clasificar(datos, modal_sin_servicio=modal.is_visible())
    return ResultadoConsulta(
        busqueda,
        resultado,
        tramites=nombres_tramites(datos),
        detalle=str(datos.get("DetalleAdicional")),
    )


def _esperar_respuesta_clasificable(
    pagina: Page, respuestas: list[Response], marca: int, tiempo_maximo_s: float
) -> dict:
    """Lee los cuerpos fuera del manejador: en la API síncrona, leerlos allí se bloquea."""
    limite = time.monotonic() + tiempo_maximo_s
    revisadas = marca
    while time.monotonic() < limite:
        for respuesta in respuestas[revisadas:]:
            revisadas += 1
            if respuesta.status != 200:
                raise _ErrorHttp(f"HTTP {respuesta.status} en ValidadorValidar")
            datos = decodificar_respuesta(respuesta.text())
            if es_clasificable(datos):
                return datos
        pagina.wait_for_timeout(200)
    raise PlaywrightTimeoutError("El servidor no respondió al seleccionar el servicio")


def pulsar_texto(pagina: Page, texto: str) -> None:
    """Las opciones son `div` sin rol y pueden quedar fuera de la pantalla.

    Algunos rótulos separan las palabras con `<br>` («Persona<br>Natural»), y su
    texto queda sin espacio, y otros terminan en punto («Devoluciones.»). El
    patrón admite ambos casos.
    """
    patron = r"\s*".join(re.escape(palabra) for palabra in texto.split())
    elemento = pagina.get_by_text(re.compile(rf"^{patron}\.?$")).locator("visible=true").first
    elemento.wait_for(state="visible")
    elemento.scroll_into_view_if_needed()
    elemento.click()


def esperar_carga(pagina: Page) -> None:
    pagina.get_by_text("Cargando", exact=False).locator("visible=true").first.wait_for(
        state="hidden"
    )


def _servicios_visibles(pagina: Page) -> str:
    """Ayuda a distinguir un servicio que no se ofrece de un cambio en el sitio."""
    try:
        servicios = pagina.locator(".btnCategoria").all_inner_texts()
    except Error:
        return ""
    nombres = [" ".join(servicio.split()) for servicio in servicios]
    return f"Servicios visibles: {nombres}" if nombres else ""


def _capturar(pagina: Page, dir_capturas: Path) -> Path | None:
    dir_capturas.mkdir(parents=True, exist_ok=True)
    ruta = dir_capturas / f"{datetime.now():%Y%m%d-%H%M%S}.png"
    try:
        pagina.screenshot(path=ruta, full_page=True)
    except Error:
        return None
    return ruta
