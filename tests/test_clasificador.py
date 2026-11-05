from pathlib import Path

import pytest

from monitor_dian.clasificador import (
    Resultado,
    clasificar,
    decodificar_respuesta,
    es_clasificable,
    nombres_tramites,
)

FIXTURES = Path(__file__).parent / "fixtures"


def cargar(nombre: str) -> dict:
    return decodificar_respuesta((FIXTURES / nombre).read_text(encoding="utf-8"))


def test_sin_servicio():
    assert clasificar(cargar("sin_servicio.json"), True) is Resultado.SIN_SERVICIO


def test_disponible_con_tramites():
    datos = cargar("disponible.json")
    assert clasificar(datos, False) is Resultado.DISPONIBLE
    assert nombres_tramites(datos) == ["Tramite de prueba"]


def test_servidor_y_modal_que_no_coinciden_son_desconocidos():
    assert clasificar(cargar("sin_servicio.json"), False) is Resultado.RESPUESTA_DESCONOCIDA
    assert clasificar(cargar("disponible.json"), True) is Resultado.RESPUESTA_DESCONOCIDA


@pytest.mark.parametrize(
    "datos",
    [
        None,
        {},
        {"Encontrado": True, "DetalleAdicional": "manejadorNuevo"},
        {"Encontrado": False, "DetalleAdicional": "manejadorEncontroColas"},
        {"Encontrado": "false", "DetalleAdicional": "manejadorNoEncontroColas"},
    ],
)
def test_valores_desconocidos(datos):
    assert clasificar(datos, False) is Resultado.RESPUESTA_DESCONOCIDA
    assert clasificar(datos, True) is Resultado.RESPUESTA_DESCONOCIDA


@pytest.mark.parametrize(
    "cuerpo", ["", "no es json", "{}", '{"d": null}', '{"d": "no es json"}', '{"d": "[1]"}']
)
def test_cuerpos_malformados(cuerpo):
    assert decodificar_respuesta(cuerpo) is None


def test_solo_son_clasificables_los_manejadores():
    assert es_clasificable(cargar("sin_servicio.json"))
    assert not es_clasificable({"DetalleAdicional": "otro"})
    assert not es_clasificable({"DetalleAdicional": None})
    assert not es_clasificable(None)
