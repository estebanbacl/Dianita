from playwright.sync_api import Error, Locator, Page

from .clasificador import TEXTO_MODAL_SIN_SERVICIO
from .flujo import Busqueda, abrir_hasta_modalidad, esperar_carga, pulsar_texto

ESPERA_SONDEO_MS = 500


class ReservaDetenida(Exception):
    """El flujo no puede seguir solo: la persona continúa en la ventana abierta."""


def avanzar_hasta_captcha(pagina: Page, busqueda: Busqueda, tramite: str = "") -> None:
    """Elige la primera fecha y hora libres. Nunca toca el captcha ni escribe datos."""
    abrir_hasta_modalidad(pagina, busqueda)
    pulsar_texto(pagina, busqueda.servicio)

    selector_tramite = pagina.locator("div[nombre='Servicios'] select")
    modal = pagina.get_by_text(TEXTO_MODAL_SIN_SERVICIO).first
    pagina.locator("div[nombre='Servicios']").or_(modal).first.wait_for(state="visible")
    if modal.is_visible():
        raise ReservaDetenida("El sitio ya no ofrece trámites para este servicio.")

    _elegir_tramite(pagina, selector_tramite, tramite)
    _avanzar_a(pagina, "div[nombre='txtPasoDos']")

    boton_fecha = pagina.locator("div[nombre='btnFecha']")
    boton_fecha.wait_for(state="visible")
    boton_fecha.click()
    esperar_carga(pagina)
    dias = pagina.locator("td.k-calendar-td:not(.k-disabled)")
    if dias.count():
        dias.first.click()
    else:
        print("No hay fechas libres en el mes visible: revise otros meses en el calendario.")
        _esperar_hasta(pagina, lambda: boton_fecha.inner_text().strip() != "")

    selector_hora = pagina.locator("div[nombre='Horas'] select")
    selector_hora.wait_for(state="visible")
    _esperar_hasta(pagina, lambda: selector_hora.locator("option").count() > 1)
    selector_hora.select_option(index=1)
    esperar_carga(pagina)
    print(f"Fecha {boton_fecha.inner_text().strip()}, hora {selector_hora.input_value()}.")

    _avanzar_a(pagina, "div[nombre='Captcha']")


def _elegir_tramite(pagina: Page, selector: Locator, tramite: str) -> None:
    opciones = [t.strip() for t in selector.locator("option").all_text_contents() if t.strip()]
    if tramite and tramite in opciones:
        selector.select_option(label=tramite)
    elif len(opciones) == 1:
        selector.select_option(index=1)
    else:
        print(f"Elija el trámite en el navegador. Opciones: {opciones}")
        _esperar_hasta(pagina, lambda: selector.input_value() != "")
    esperar_carga(pagina)


def _avanzar_a(pagina: Page, destino: str) -> None:
    pulsar_texto(pagina, "Siguiente")
    esperar_carga(pagina)
    # Otras pantallas ocultas repiten nombres, como el captcha de «Gestionar cita».
    pagina.locator(destino).locator("visible=true").first.wait_for(state="visible")


def _esperar_hasta(pagina: Page, condicion) -> None:
    while not condicion():
        pagina.wait_for_timeout(ESPERA_SONDEO_MS)


def acompanar_formulario(pagina: Page, numero_documento: str) -> None:
    """Rellena el documento cada vez que el captcha lo revela, hasta que se cierre la ventana."""
    campo = pagina.locator("div[nombre='tbxNumeroDoc'] input").locator("visible=true").first
    relleno = False
    print("Resuelva el captcha en el navegador.")
    while not pagina.is_closed():
        visible = campo.is_visible()
        if visible and not relleno:
            if numero_documento:
                campo.fill(numero_documento)
                print("Revise los datos, complete lo que falte y confirme.")
            else:
                print("DIAN_NUMERO_DOCUMENTO está vacío en .env: escríbalo en el navegador.")
            relleno = True
        elif not visible and relleno:
            print("El captcha caducó: resuélvalo de nuevo.")
            relleno = False
        pagina.wait_for_timeout(ESPERA_SONDEO_MS)


def reservar(navegador, busqueda: Busqueda, tramite: str, numero_documento: str, tiempo_maximo_s: float) -> None:
    """Pase lo que pase, la ventana sigue abierta hasta que la persona la cierre."""
    pagina = navegador.new_context(no_viewport=True).new_page()
    pagina.set_default_timeout(tiempo_maximo_s * 1000)
    try:
        try:
            avanzar_hasta_captcha(pagina, busqueda, tramite)
        except ReservaDetenida as motivo:
            print(motivo)
            pagina.wait_for_event("close", timeout=0)
            return
        except Exception as error:
            print(f"Automatización detenida ({type(error).__name__}): continúe en la ventana.")
            pagina.wait_for_event("close", timeout=0)
            return
        acompanar_formulario(pagina, numero_documento)
    except Error:
        if not pagina.is_closed():
            raise
