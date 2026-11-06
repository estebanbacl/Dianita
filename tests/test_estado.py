from datetime import datetime, timedelta

import pytest

from monitor_dian import estado as registro
from monitor_dian.clasificador import Resultado
from monitor_dian.estado import Estado, aplicar_resultado, dentro_de_pausa_horaria
from monitor_dian.flujo import Busqueda, ResultadoConsulta

AHORA = datetime(2026, 11, 5, 12, 0)


def aplicar(estado, resultado, ahora=AHORA, detalle=""):
    return aplicar_resultado(estado, resultado, detalle, ahora, errores_para_avisar=3)


def test_el_tercer_error_seguido_avisa():
    estado = Estado()
    assert aplicar(estado, Resultado.ERROR_FLUJO) is None
    assert aplicar(estado, Resultado.ERROR_RED) is None
    assert "no está funcionando" in aplicar(estado, Resultado.ERROR_FLUJO)


def test_una_consulta_correcta_reinicia_el_contador():
    estado = Estado(errores_seguidos=2)
    aplicar(estado, Resultado.SIN_SERVICIO)
    assert estado.errores_seguidos == 0
    assert aplicar(estado, Resultado.ERROR_FLUJO) is None


def test_el_aviso_de_error_se_repite_como_maximo_cada_24_horas():
    estado = Estado(errores_seguidos=3)
    assert aplicar(estado, Resultado.ERROR_FLUJO) is not None
    assert aplicar(estado, Resultado.ERROR_FLUJO, AHORA + timedelta(hours=23)) is None
    assert aplicar(estado, Resultado.ERROR_FLUJO, AHORA + timedelta(hours=24)) is not None


def test_una_respuesta_desconocida_avisa_de_inmediato():
    assert aplicar(Estado(), Resultado.RESPUESTA_DESCONOCIDA) is not None


def test_disponible_pausa_y_sin_servicio_no():
    estado = Estado()
    aplicar(estado, Resultado.SIN_SERVICIO)
    assert not estado.pausado
    aplicar(estado, Resultado.DISPONIBLE)
    assert estado.pausado


def test_un_rechazo_del_sitio_pausa_y_avisa():
    estado = Estado()
    assert aplicar(estado, Resultado.ERROR_RED, detalle="HTTP 429 al abrir el sitio") is not None
    assert estado.pausado


@pytest.mark.parametrize(
    "hora, esperado",
    [("00:59", False), ("01:00", True), ("04:59", True), ("05:00", False), ("12:00", False)],
)
def test_pausa_horaria(hora, esperado):
    ahora = datetime.strptime(hora, "%H:%M")
    assert dentro_de_pausa_horaria(ahora, "01:00", "05:00") is esperado


def test_pausa_horaria_que_cruza_la_medianoche():
    assert dentro_de_pausa_horaria(datetime(2026, 1, 1, 23, 30), "23:00", "02:00")
    assert not dentro_de_pausa_horaria(datetime(2026, 1, 1, 12, 0), "23:00", "02:00")


def test_guardar_y_cargar(tmp_path):
    ruta = tmp_path / "estado.json"
    assert registro.cargar(ruta) == Estado()
    registro.guardar(ruta, Estado(pausado=True, errores_seguidos=2))
    assert registro.cargar(ruta) == Estado(pausado=True, errores_seguidos=2)


def test_el_historial_solo_tiene_datos_de_la_busqueda(tmp_path):
    ruta = tmp_path / "historial.jsonl"
    consulta = ResultadoConsulta(
        Busqueda("Persona Natural", "Videoatención", "Devoluciones"), Resultado.SIN_SERVICIO
    )
    registro.agregar_historial(ruta, AHORA, consulta)
    assert "Devoluciones" in ruta.read_text(encoding="utf-8")
    assert "Persona Natural" not in ruta.read_text(encoding="utf-8")


def test_el_bloqueo_impide_ejecuciones_simultaneas(tmp_path):
    ruta = tmp_path / "consulta.lock"
    with registro.bloqueo(ruta):
        with pytest.raises(registro.YaEnEjecucion):
            with registro.bloqueo(ruta):
                pass
    with registro.bloqueo(ruta):
        pass
