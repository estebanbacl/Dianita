import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request


def enviar(titulo: str, mensaje: str, entorno: dict[str, str]) -> dict[str, str]:
    """Intenta todos los canales configurados y devuelve el resultado de cada uno."""
    resultados = {"escritorio": _intentar(_escritorio, titulo, mensaje)}
    token = entorno.get("TELEGRAM_BOT_TOKEN")
    chat = entorno.get("TELEGRAM_CHAT_ID")
    if token and chat:
        resultados["telegram"] = _intentar(_telegram, token, chat, f"{titulo}\n{mensaje}")
    else:
        resultados["telegram"] = "sin configurar"
    return resultados


def _intentar(canal, *argumentos) -> str:
    try:
        canal(*argumentos)
    except Exception as error:
        return f"falló: {type(error).__name__}"
    return "enviado"


def _escritorio(titulo: str, mensaje: str) -> None:
    if sys.platform == "darwin":
        # Los textos van como argumentos para que nunca se interpreten como código.
        comando = [
            "osascript",
            "-e", "on run argv",
            "-e", 'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"',
            "-e", "end run",
            titulo,
            mensaje,
        ]
    elif sys.platform == "win32":
        comando = ["msg", "*", f"{titulo}: {mensaje}"]
    elif shutil.which("notify-send"):
        comando = ["notify-send", "--urgency=critical", titulo, mensaje]
    else:
        raise RuntimeError("no hay un comando de notificación disponible")
    subprocess.run(comando, check=True, capture_output=True, timeout=30)


def _telegram(token: str, chat: str, texto: str) -> None:
    datos = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
    solicitud = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=datos
    )
    with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
        if not json.load(respuesta).get("ok"):
            raise RuntimeError("Telegram rechazó el mensaje")
