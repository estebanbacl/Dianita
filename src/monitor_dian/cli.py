import argparse
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import Error, sync_playwright

from . import avisos
from . import config as configuracion
from . import estado as registro
from .clasificador import Resultado
from .flujo import Busqueda, ResultadoConsulta, consultar
from .reserva import reservar

RAIZ = Path(__file__).resolve().parents[2]
RUTA_ENV = RAIZ / ".env"
RUTA_ESTADO = RAIZ / "datos" / "estado.json"
RUTA_HISTORIAL = RAIZ / "datos" / "historial.jsonl"
RUTA_BLOQUEO = RAIZ / "datos" / "consulta.lock"
DIR_CAPTURAS = RAIZ / "capturas"
SEGUNDOS_ANTES_DE_REINTENTAR = 300
PERSONA = "Persona Natural"
# Son dos porque la disponibilidad de un servicio cambia durante el día.
CONTROLES = [
    Busqueda(PERSONA, "Presencial", "RUT y orientación TAC"),
    Busqueda(PERSONA, "Videoatención", "Defensoría"),
]
COMBINACIONES_DIAGNOSTICO = [
    Busqueda(PERSONA, "Videoatención", "Devoluciones"),
    Busqueda(PERSONA, "Presencial", "Devoluciones"),
    *CONTROLES,
]


def _busqueda(config: dict) -> Busqueda:
    seccion = config["busqueda"]
    return Busqueda(seccion["persona"], seccion["modalidad"], seccion["servicio"])


def _ahora(config: dict) -> datetime:
    return datetime.now(ZoneInfo(config["programacion"]["zona_horaria"]))


def _avisar(titulo: str, mensaje: str) -> None:
    entorno = configuracion.cargar_entorno(RUTA_ENV, prefijo="TELEGRAM_")
    for canal, resultado in avisos.enviar(titulo, mensaje, entorno).items():
        print(f"Aviso por {canal}: {resultado}")


def _consultar_una_vez(busqueda: Busqueda, tiempo_maximo: float) -> ResultadoConsulta:
    try:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch(headless=True)
            try:
                return consultar(navegador, busqueda, tiempo_maximo, DIR_CAPTURAS)
            finally:
                navegador.close()
    except Error as error:
        detalle = error.message.splitlines()[0]
        return ResultadoConsulta(busqueda, Resultado.ERROR_FLUJO, detalle=detalle)


def comando_consultar(config: dict, sin_retraso: bool) -> int:
    estado = registro.cargar(RUTA_ESTADO)
    if estado.pausado:
        print("El monitor está pausado. Use `monitor reanudar` para continuar.")
        return 0
    programacion = config["programacion"]
    if registro.dentro_de_pausa_horaria(
        _ahora(config), programacion["sin_consultas_desde"], programacion["sin_consultas_hasta"]
    ):
        print("Dentro de la ventana sin consultas.")
        return 0

    if not sin_retraso:
        time.sleep(random.uniform(0, programacion["retraso_maximo_minutos"] * 60))

    try:
        with registro.bloqueo(RUTA_BLOQUEO):
            consulta = _consultar_con_reintento(config)
            ahora = _ahora(config)
            registro.agregar_historial(RUTA_HISTORIAL, ahora, consulta)
            aviso_error = registro.aplicar_resultado(
                estado,
                consulta.resultado,
                consulta.detalle,
                ahora,
                config["flujo"]["errores_para_avisar"],
            )
            registro.guardar(RUTA_ESTADO, estado)
    except registro.YaEnEjecucion:
        print("Ya hay una consulta en ejecución.")
        return 0

    _mostrar(consulta)
    if aviso_error:
        _avisar("Monitor DIAN: revisar", aviso_error)
    if consulta.resultado is Resultado.DISPONIBLE:
        tramites = ", ".join(t.strip() for t in consulta.tramites) or "sin detalle"
        _avisar(
            "¡Hay trámites en la DIAN!",
            f"{ahora:%H:%M}. {consulta.busqueda.servicio}: {tramites}. "
            "Se abrió el navegador: resuelva el captcha y confirme.",
        )
        return comando_reservar(config, None)
    return 0


def _consultar_con_reintento(config: dict) -> ResultadoConsulta:
    busqueda = _busqueda(config)
    tiempo_maximo = config["flujo"]["tiempo_maximo_paso_segundos"]
    consulta = _consultar_una_vez(busqueda, tiempo_maximo)
    if consulta.resultado is Resultado.ERROR_RED and not registro.es_bloqueo(
        consulta.resultado, consulta.detalle
    ):
        time.sleep(SEGUNDOS_ANTES_DE_REINTENTAR)
        consulta = _consultar_una_vez(busqueda, tiempo_maximo)
    return consulta


def comando_reservar(config: dict, servicio: str | None) -> int:
    busqueda = _busqueda(config)
    tramite = config["busqueda"]["tramite"]
    if servicio:
        busqueda = Busqueda(busqueda.persona, busqueda.modalidad, servicio)
        tramite = ""
    numero_documento = configuracion.cargar_entorno(RUTA_ENV, prefijo="DIAN_").get(
        "DIAN_NUMERO_DOCUMENTO", ""
    )
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=False)
        try:
            reservar(
                navegador,
                busqueda,
                tramite,
                numero_documento,
                config["flujo"]["tiempo_maximo_paso_segundos"],
            )
        finally:
            navegador.close()
    print("Ventana cerrada. Si no reservó, use `monitor reanudar` para seguir consultando.")
    return 0


def comando_estado() -> int:
    estado = registro.cargar(RUTA_ESTADO)
    print(f"Estado: {'PAUSADO' if estado.pausado else 'ACTIVO'}")
    print(f"Última consulta: {estado.ultima_consulta or 'ninguna'}")
    print(f"Último resultado: {estado.ultimo_resultado or 'ninguno'}")
    print(f"Errores seguidos: {estado.errores_seguidos}")
    if RUTA_HISTORIAL.exists():
        print("Últimas consultas:")
        for linea in RUTA_HISTORIAL.read_text(encoding="utf-8").splitlines()[-5:]:
            print(f"  {linea}")
    return 0


def comando_reanudar() -> int:
    estado = registro.cargar(RUTA_ESTADO)
    estado.pausado = False
    estado.errores_seguidos = 0
    estado.ultimo_aviso_error = None
    registro.guardar(RUTA_ESTADO, estado)
    print("El monitor volverá a consultar en la próxima hora programada.")
    return 0


def comando_probar_aviso() -> int:
    _avisar("Monitor DIAN", "Mensaje de prueba: los avisos funcionan.")
    return 0


def comando_diagnostico(config: dict) -> int:
    tiempo_maximo = config["flujo"]["tiempo_maximo_paso_segundos"]
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=True)
        try:
            consultas = [
                consultar(navegador, busqueda, tiempo_maximo, DIR_CAPTURAS)
                for busqueda in COMBINACIONES_DIAGNOSTICO
            ]
        finally:
            navegador.close()

    for consulta in consultas:
        _mostrar(consulta)
    if not any(
        c.busqueda in CONTROLES and c.resultado is Resultado.DISPONIBLE for c in consultas
    ):
        print(
            "\nNingún control dio DISPONIBLE: no se puede concluir nada sobre Devoluciones."
        )
        return 1
    print("\nAl menos un control funcionó: los resultados de Devoluciones son fiables.")
    return 0


def _mostrar(consulta: ResultadoConsulta) -> None:
    busqueda = consulta.busqueda
    print(f"{busqueda.modalidad} / {busqueda.servicio}: {consulta.resultado.value}")
    for tramite in consulta.tramites:
        print(f"  trámite: {tramite}")
    if consulta.detalle:
        print(f"  detalle: {consulta.detalle}")
    if consulta.captura:
        print(f"  captura: {consulta.captura}")


def main() -> int:
    analizador = argparse.ArgumentParser(prog="monitor")
    analizador.add_argument("--config", type=Path, default=RAIZ / "config.toml")
    comandos = analizador.add_subparsers(dest="comando", required=True)
    consulta = comandos.add_parser("consultar", help="consulta una vez y avisa si hay trámites")
    consulta.add_argument("--sin-retraso", action="store_true", help="omite el retraso aleatorio")
    reserva = comandos.add_parser("reservar", help="abre el navegador y avanza hasta el captcha")
    reserva.add_argument("--servicio", help="otro servicio, para probar con un control")
    comandos.add_parser("estado", help="muestra el estado y las últimas consultas")
    comandos.add_parser("reanudar", help="quita la pausa y reinicia el contador de errores")
    comandos.add_parser("probar-aviso", help="envía un mensaje de prueba por cada canal")
    comandos.add_parser(
        "diagnostico", help="prueba una vez, solo lectura, Devoluciones y los controles"
    )
    argumentos = analizador.parse_args()

    if argumentos.comando == "estado":
        return comando_estado()
    if argumentos.comando == "reanudar":
        return comando_reanudar()
    if argumentos.comando == "probar-aviso":
        return comando_probar_aviso()
    config = configuracion.cargar(argumentos.config)
    if argumentos.comando == "consultar":
        return comando_consultar(config, argumentos.sin_retraso)
    if argumentos.comando == "reservar":
        return comando_reservar(config, argumentos.servicio)
    return comando_diagnostico(config)


if __name__ == "__main__":
    sys.exit(main())
