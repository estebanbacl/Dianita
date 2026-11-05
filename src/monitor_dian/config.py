import tomllib
from pathlib import Path

INTERVALO_MINIMO_MINUTOS = 60


class ConfiguracionInvalida(ValueError):
    pass


def cargar(ruta: Path) -> dict:
    with ruta.open("rb") as archivo:
        config = tomllib.load(archivo)
    validar(config)
    return config


def validar(config: dict) -> None:
    intervalo = config["programacion"]["intervalo_minutos"]
    if intervalo < INTERVALO_MINIMO_MINUTOS:
        raise ConfiguracionInvalida(
            f"intervalo_minutos debe ser al menos {INTERVALO_MINIMO_MINUTOS}; se recibió {intervalo}"
        )
