import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import config as configuracion
from .clasificador import Resultado
from .flujo import Busqueda, ResultadoConsulta, consultar

RAIZ = Path(__file__).resolve().parents[2]
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


def diagnostico(config: dict) -> int:
    tiempo_maximo = config["flujo"]["tiempo_maximo_paso_segundos"]
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=True)
        try:
            consultas = [
                consultar(navegador, busqueda, tiempo_maximo, RAIZ / "capturas")
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
    comandos.add_parser(
        "diagnostico", help="prueba una vez, solo lectura, Devoluciones y los controles"
    )
    argumentos = analizador.parse_args()
    return diagnostico(configuracion.cargar(argumentos.config))


if __name__ == "__main__":
    sys.exit(main())
