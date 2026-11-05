import json
from enum import Enum

TEXTO_MODAL_SIN_SERVICIO = (
    "No se encontraron especialidades relacionadas según los filtros seleccionados."
)
DETALLE_SIN_SERVICIO = "manejadorNoEncontroColas"
DETALLE_DISPONIBLE = "manejadorEncontroColas"
# Responde a la selección de modalidad y puede llegar después del clic en el servicio.
DETALLE_CATEGORIAS = "manejadorEncontroCategoria"


class Resultado(str, Enum):
    SIN_SERVICIO = "SIN_SERVICIO"
    DISPONIBLE = "DISPONIBLE"
    ERROR_FLUJO = "ERROR_FLUJO"
    ERROR_RED = "ERROR_RED"
    RESPUESTA_DESCONOCIDA = "RESPUESTA_DESCONOCIDA"


def decodificar_respuesta(cuerpo: str) -> dict | None:
    """El campo `d` trae otro JSON como cadena, así que se decodifica dos veces."""
    try:
        interno = json.loads(cuerpo)["d"]
        datos = json.loads(interno)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return datos if isinstance(datos, dict) else None


def es_clasificable(datos: dict | None) -> bool:
    if datos is None:
        return False
    detalle = datos.get("DetalleAdicional")
    return (
        isinstance(detalle, str)
        and detalle.startswith("manejador")
        and detalle != DETALLE_CATEGORIAS
    )


def clasificar(datos: dict | None, modal_sin_servicio: bool) -> Resultado:
    """Solo reconoce las combinaciones conocidas: lo demás nunca cuenta como «sin citas»."""
    if datos is None:
        return Resultado.RESPUESTA_DESCONOCIDA
    encontrado = datos.get("Encontrado")
    detalle = datos.get("DetalleAdicional")
    if encontrado is False and detalle == DETALLE_SIN_SERVICIO and modal_sin_servicio:
        return Resultado.SIN_SERVICIO
    if encontrado is True and detalle == DETALLE_DISPONIBLE and not modal_sin_servicio:
        return Resultado.DISPONIBLE
    return Resultado.RESPUESTA_DESCONOCIDA


def nombres_tramites(datos: dict | None) -> list[str]:
    if not datos or not isinstance(datos.get("ObjetosEncontrados"), list):
        return []
    nombres = []
    for grupo in datos["ObjetosEncontrados"]:
        for objeto in grupo if isinstance(grupo, list) else [grupo]:
            if isinstance(objeto, dict) and objeto.get("Nombre"):
                nombres.append(objeto["Nombre"])
    return nombres
