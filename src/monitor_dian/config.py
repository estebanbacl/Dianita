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


def cargar_entorno(ruta: Path, prefijo: str = "") -> dict[str, str]:
    """Lee `.env`. Con `prefijo`, deja fuera lo demás para no cargar datos personales."""
    if not ruta.exists():
        return {}
    entorno = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip("\"'")
        if valor and clave.startswith(prefijo):
            entorno[clave] = valor
    return entorno


def validar(config: dict) -> None:
    intervalo = config["programacion"]["intervalo_minutos"]
    if intervalo < INTERVALO_MINIMO_MINUTOS:
        raise ConfiguracionInvalida(
            f"intervalo_minutos debe ser al menos {INTERVALO_MINIMO_MINUTOS}; se recibió {intervalo}"
        )
