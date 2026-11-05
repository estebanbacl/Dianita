import pytest

from monitor_dian.config import ConfiguracionInvalida, validar


def test_rechaza_intervalos_menores_de_60_minutos():
    with pytest.raises(ConfiguracionInvalida):
        validar({"programacion": {"intervalo_minutos": 59}})


def test_acepta_60_minutos():
    validar({"programacion": {"intervalo_minutos": 60}})
