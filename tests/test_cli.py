from monitor_dian import cli
from monitor_dian import estado as registro
from monitor_dian.clasificador import Resultado
from monitor_dian.config import cargar_entorno
from monitor_dian.estado import Estado
from monitor_dian.flujo import ResultadoConsulta

CONFIG = {
    "busqueda": {
        "persona": "Persona Natural",
        "modalidad": "Videoatención",
        "servicio": "Devoluciones",
        "tramite": "",
    },
    "programacion": {
        "retraso_maximo_minutos": 0,
        "sin_consultas_desde": "00:00",
        "sin_consultas_hasta": "00:00",
        "zona_horaria": "America/Bogota",
    },
    "flujo": {"tiempo_maximo_paso_segundos": 1, "errores_para_avisar": 3},
}


def preparar(monkeypatch, tmp_path, resultado):
    monkeypatch.setattr(cli, "RUTA_ESTADO", tmp_path / "estado.json")
    monkeypatch.setattr(cli, "RUTA_HISTORIAL", tmp_path / "historial.jsonl")
    monkeypatch.setattr(cli, "RUTA_BLOQUEO", tmp_path / "consulta.lock")
    llamadas = {"consultas": 0, "avisos": [], "reservas": 0}

    def consultar_falso(busqueda, _tiempo):
        llamadas["consultas"] += 1
        return ResultadoConsulta(busqueda, resultado, tramites=["Trámite"])

    def reservar_falso(_config, _servicio):
        llamadas["reservas"] += 1
        return 0

    monkeypatch.setattr(cli, "_consultar_una_vez", consultar_falso)
    monkeypatch.setattr(cli, "comando_reservar", reservar_falso)
    monkeypatch.setattr(cli, "_avisar", lambda titulo, _m: llamadas["avisos"].append(titulo))
    return llamadas


def test_pausado_impide_consultar(monkeypatch, tmp_path):
    llamadas = preparar(monkeypatch, tmp_path, Resultado.SIN_SERVICIO)
    registro.guardar(cli.RUTA_ESTADO, Estado(pausado=True))
    cli.comando_consultar(CONFIG, sin_retraso=True)
    assert llamadas["consultas"] == 0


def test_sin_servicio_no_avisa(monkeypatch, tmp_path):
    llamadas = preparar(monkeypatch, tmp_path, Resultado.SIN_SERVICIO)
    cli.comando_consultar(CONFIG, sin_retraso=True)
    assert llamadas["consultas"] == 1
    assert llamadas["avisos"] == []
    assert llamadas["reservas"] == 0


def test_disponible_avisa_una_vez_pausa_y_reserva(monkeypatch, tmp_path):
    llamadas = preparar(monkeypatch, tmp_path, Resultado.DISPONIBLE)
    cli.comando_consultar(CONFIG, sin_retraso=True)
    cli.comando_consultar(CONFIG, sin_retraso=True)
    assert llamadas["consultas"] == 1
    assert len(llamadas["avisos"]) == 1
    assert llamadas["reservas"] == 1
    assert registro.cargar(cli.RUTA_ESTADO).pausado


def test_el_prefijo_deja_fuera_los_datos_personales(tmp_path):
    ruta = tmp_path / ".env"
    ruta.write_text("DIAN_NUMERO_DOCUMENTO=123\nTELEGRAM_CHAT_ID=9\nTELEGRAM_BOT_TOKEN=\n")
    assert cargar_entorno(ruta, prefijo="TELEGRAM_") == {"TELEGRAM_CHAT_ID": "9"}
