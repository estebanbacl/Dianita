# Monitor de citas DIAN

Consulta cada hora si hay cita de **Devoluciones por Videoatención** para Persona Natural. Cuando aparece, avisa, deja de consultar y abre un navegador visible que elige la primera fecha y hora libres y se detiene en el captcha.

**La persona resuelve el captcha y da la confirmación final.** La herramienta no hace ninguna de las dos cosas.

La especificación completa está en [ESPECIFICACION-monitor-citas-dian.md](ESPECIFICACION-monitor-citas-dian.md).

## Instalación

Requiere Python 3.11 o superior.

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -e ".[dev]"
```

```bash
.venv/bin/playwright install chromium
```

```bash
cp .env.ejemplo .env && chmod 600 .env
```

Complete `.env` con sus datos. Nunca se versiona y solo `reservar` usa los datos personales.

## Avisos por Telegram (recomendado)

1. Cree un bot con @BotFather y copie el token en `TELEGRAM_BOT_TOKEN`.
2. Escríbale un mensaje al bot.
3. Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` y copie `chat.id` en `TELEGRAM_CHAT_ID`.
4. Compruébelo:

```bash
.venv/bin/monitor probar-aviso
```

## Consulta cada hora en macOS

```bash
sh programacion/instalar-macos.sh
```

Para desinstalarla:

```bash
sh programacion/instalar-macos.sh --desinstalar
```

El Mac debe estar encendido, sin suspenderse y con la sesión iniciada. Si se suspende, no consulta mientras duerme y al despertar hace como máximo una consulta.

En Linux, use un temporizador de `systemd --user` o `cron` con `DISPLAY` y `DBUS_SESSION_BUS_ADDRESS`. En Windows, use el Programador de tareas con «Ejecutar solo cuando el usuario haya iniciado sesión». Estas dos opciones aún no se han probado.

## Comandos

| Comando | Función |
|---|---|
| `monitor consultar` | Consulta una vez y, si hay trámites, avisa, pausa y abre el navegador |
| `monitor reservar` | Abre el navegador y avanza hasta el captcha |
| `monitor reservar --servicio Defensoría` | Lo mismo, con otro servicio, para probar el recorrido |
| `monitor estado` | Muestra el estado y las últimas consultas |
| `monitor reanudar` | Quita la pausa, por ejemplo si no quedó reservada la cita |
| `monitor diagnostico` | Prueba Devoluciones y los controles una vez |
| `monitor probar-aviso` | Envía un mensaje de prueba por cada canal |

Los comandos están en `.venv/bin/`. Tras un aviso, el monitor queda pausado hasta usar `monitor reanudar`.

## Pruebas

```bash
.venv/bin/pytest
```
