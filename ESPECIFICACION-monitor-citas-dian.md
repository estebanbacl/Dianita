# Monitor de citas DIAN: plan y especificación

**Estado:** listo para construir. Aún no existe código.
**Fecha de la revisión del sitio:** 2026-11-05
**Sitio:** https://agendamiento.dian.gov.co/

Este documento es autosuficiente: quien lo construya (una persona o Claude Code) no necesita ningún otro contexto.

---

## 1. Objetivo

Consultar una vez por hora si existe cita para esta combinación:

| Campo | Valor |
|---|---|
| Tipo de persona | Persona Natural |
| Tipo de cita | Videoatención |
| Tipo de servicio | Devoluciones |

Cuando haya disponibilidad, la herramienta avisa de inmediato, deja de consultar y abre un navegador visible, avanzado hasta donde sea posible, para que la persona usuaria termine la reserva.

### Fuera de alcance

- **Resolver o evadir el reCAPTCHA.** No usar servicios de resolución, modelos de visión, técnicas de evasión de detección ni llamadas directas que se salten el formulario.
- **Confirmar la cita sin una persona.** El clic final siempre lo hace la persona usuaria.
- **Consultar más de una vez por hora** de forma programada.

---

## 2. Hallazgos del sitio

### 2.1 Comprobado el 2026-11-05

**Flujo y resultado**

1. La página de inicio muestra «Agendar cita» y «Gestionar cita».
2. «Agendar cita» lleva al paso «Tipo de persona, cita, servicio y trámite».
3. Las opciones aparecen de forma progresiva: al elegir persona aparece «¿Cómo prefiere la cita?», y al elegir el tipo de cita aparece «Seleccione el tipo de servicio».
4. Con Natural + Videoatención + **Devoluciones**, aparece un modal con este texto: «No se encontraron especialidades relacionadas según los filtros seleccionados.» Su botón es «Aceptar».
5. Al pulsar «Aceptar», el sitio vuelve a la página de inicio y se pierde la selección.
6. Con Natural + Videoatención + **RUT y orientación TAC**, aparece una sección «Trámite» con una opción. Este caso sirvió como control positivo.

**Señal del servidor**

Cada selección dispara `POST https://agendamiento.dian.gov.co/Player.aspx/ValidadorValidar`. La respuesta es JSON, y el campo `d` contiene **otro JSON como cadena de texto**, así que hay que decodificarlo dos veces.

Sin servicio (Devoluciones):

```json
{"Encontrado": false, "ObjetosEncontrados": null, "TotalObjetosEncontrados": 0, "DetalleAdicional": "manejadorNoEncontroColas"}
```

Con servicio (RUT, resumido):

```json
{"Encontrado": true, "ObjetosEncontrados": [[{"IdEspecialidad": 336, "Nombre": "...", "TipoEspecialidad": "2", "Llave": "336"}]], "TotalObjetosEncontrados": 1, "DetalleAdicional": "manejadorEncontroColas"}
```

**Características técnicas**

- La aplicación es de una sola página (WebPlayer de Ciel Ingeniería, con Kendo UI y jQuery). La URL no cambia entre pasos.
- La carga es lenta: tras pulsar «Agendar cita», la capa «Cargando» duró más de 10 segundos. Cada selección tardó varios segundos más.
- El árbol de accesibilidad salió vacío, y al menos los botones de opción son `div`. Conviene localizar los elementos por **texto visible**, no por rol.
- `captcha.min.js` muestra un reCAPTCHA v2 con casilla en la pantalla `PasoTres`.
- El contenedor `divPasoTresNumeroDocumento`, con el campo `div[nombre="tbxNumeroDoc"] input`, **solo se muestra después de resolver el captcha**.
- Si el captcha caduca, el campo se oculta y se vacía, y el captcha se reinicia.
- El flujo «Gestionar cita» también tiene captcha (pantalla `DatosGestionCita`), pero queda fuera de alcance.

### 2.2 No comprobado

| Incógnita | Por qué importa | Cómo resolverla |
|---|---|---|
| Qué ocurre después de la sección «Trámite» | Devoluciones no deja avanzar, y en el control con RUT no se pasó de ahí | Explorarlo en el hito 1 sin enviar datos, con un servicio que sí avance |
| En qué paso se ve la falta de cupos | `manejadorEncontroColas` indica que hay trámites, **no necesariamente que haya fechas libres** | Igual que la anterior. Los archivos `listaCiudades`, `listaSedes`, `botonFecha`, `listaHoras` y `grillaCitas` sugieren esos pasos, pero es una inferencia |
| Si Devoluciones se ofrece por videoatención | El mensaje habla de «especialidades», no de cupos. Si no se ofrece, consultar nunca dará resultado | Llamar al Contact Center: 57 601 489 9000 |
| Si Devoluciones existe en modalidad Presencial | Sería una alternativa | Comando `diagnostico` (sección 4.6) |
| Hora de publicación de los cupos | Permitiría ajustar el horario | Preguntar a la DIAN o revisar el historial acumulado |
| Cuál es el cuerpo de la petición `ValidadorValidar` | No se capturó y no hace falta: se debe usar el flujo de la interfaz | No aplica |
| Qué dicen los términos de uso sobre el acceso automatizado | Conviene conocerlos antes de dejarlo en marcha | Leer «Políticas de privacidad y términos de uso» en el pie del sitio |

---

## 3. Arquitectura

**Stack:** Python 3.11+ y Playwright (Chromium). Funciona en macOS, Windows y Linux.

```text
Programador del sistema (cada hora)
        │
        ▼
   monitor consultar ──► navegador sin interfaz ──► sitio DIAN
        │
        ├─ clasifica el resultado y lo añade al historial
        │
        ├─ SIN_SERVICIO ──► termina
        ├─ ERROR ─────────► captura pantalla; avisa tras 3 errores seguidos
        └─ DISPONIBLE ────► avisa, guarda estado PAUSADO y abre el navegador visible
                                   │
                                   ▼
                     La persona resuelve el captcha y confirma
```

### Estructura de archivos

```text
monitor-citas-dian/
├── README.md
├── pyproject.toml
├── .gitignore              # excluye .env, datos/ y capturas/
├── .env.ejemplo
├── config.toml
├── src/monitor_dian/
│   ├── cli.py              # consultar, reservar, estado, reanudar, diagnostico, probar-aviso
│   ├── flujo.py            # navegación con Playwright
│   ├── clasificador.py     # interpreta las respuestas del servidor
│   ├── avisos.py           # escritorio y Telegram
│   └── estado.py           # estado e historial
├── tests/
│   └── fixtures/           # respuestas de la sección 2.1
├── programacion/           # plantillas de launchd, cron y Programador de tareas
└── datos/                  # estado.json, historial.jsonl (no versionado)
```

---

## 4. Especificación funcional

### 4.1 Consulta (`monitor consultar`)

1. Si el estado es `PAUSADO`, termina sin abrir el sitio.
2. Abre el sitio con un navegador sin interfaz y registra las respuestas de `ValidadorValidar`.
3. Pulsa «Agendar cita» y espera a que «Cargando» desaparezca y a que se vea «Persona Natural».
4. Selecciona, esperando entre un paso y otro a que aparezca el siguiente:
   «Persona Natural» → «Videoatención» → «Devoluciones».
5. Clasifica la respuesta que siguió al clic en «Devoluciones».
6. Añade el resultado al historial y cierra el navegador.

**Requisitos**

- Lee `persona`, `modalidad` y `servicio` desde `config.toml`.
- Espera por condiciones, no por tiempos fijos. El tiempo máximo por paso es de 60 s y es configurable.
- Desplaza cada elemento a la vista antes de pulsarlo, porque las opciones quedan fuera de la pantalla.
- Usa un contexto de navegador nuevo en cada consulta.
- Usa el agente de usuario predeterminado de Playwright, sin técnicas de ocultación.

### 4.2 Clasificación

| Resultado | Condición | Acción |
|---|---|---|
| `SIN_SERVICIO` | `Encontrado=false` y `DetalleAdicional=manejadorNoEncontroColas` | Registrar y terminar |
| `DISPONIBLE` | `Encontrado=true` y `DetalleAdicional=manejadorEncontroColas` | Avisar y pausar (4.3) |
| `ERROR_FLUJO` | No aparece un texto esperado o se agota el tiempo | Captura de pantalla y registro |
| `ERROR_RED` | Fallo de red o HTTP distinto de 200 | Registro; un solo reintento tras 5 min |
| `RESPUESTA_DESCONOCIDA` | Cualquier otra combinación | Guardar la respuesta, captura y aviso inmediato |

**Regla clave:** un fallo nunca se clasifica como «sin citas». Tras **3 errores seguidos**, se envía un aviso con el mensaje «el monitor no está funcionando». Se repite como máximo una vez cada 24 horas y se reinicia con cualquier consulta correcta.

La respuesta clasificable es la que tenga un `DetalleAdicional` de la forma `manejador*` y llegue después del clic en el servicio. Como comprobación adicional, si el servidor dice `SIN_SERVICIO`, el modal debe mostrar el texto de la sección 2.1. Si ambos no coinciden, el resultado es `RESPUESTA_DESCONOCIDA`.

### 4.3 Al detectar disponibilidad

1. Enviar el aviso por **todos** los canales configurados, indicando la hora y los trámites encontrados (`Nombre`).
2. Guardar el estado `PAUSADO`, para no repetir avisos ni abrir más navegadores cada hora.
3. Ejecutar `monitor reservar`.

### 4.4 Reserva asistida (`monitor reservar`)

1. Abre Chromium **visible** y repite el flujo de la sección 4.1.
2. Selecciona el trámite configurado. Si solo hay uno, lo selecciona. Si hay varios y ninguno está configurado, se detiene para que elija la persona.
3. Avanza por los pasos siguientes usando las preferencias de `config.toml` (ciudad, sede, primera fecha libre), una vez verificados en el hito 1. Ante cualquier elemento inesperado, deja de automatizar y **mantiene abierta la ventana**.
4. Al llegar al captcha, se detiene y muestra: «Resuelva el captcha en el navegador».
5. Espera a que `divPasoTresNumeroDocumento` sea visible y rellena los datos desde `.env`.
6. Si el captcha caduca y el campo se oculta, vuelve a esperar y rellena otra vez.
7. **Nunca pulsa el botón final de confirmación.** Muestra: «Revise los datos y confirme».
8. El navegador permanece abierto hasta que la persona lo cierre, sin importar lo que falle.

**Comprobación de cupos:** si en esos pasos se ve que no hay fechas libres, el comando lo informa y deja el estado en `PAUSADO`. Una vez conocido ese paso, se puede ampliar `consultar` para que lo detecte sin intervención (hito 4).

### 4.5 Avisos

| Canal | Requisito | Prioridad |
|---|---|---|
| Notificación de escritorio con sonido | Obligatorio | Hito 2 |
| Telegram (token y chat en `.env`) | Muy recomendado, porque la cita puede ocuparse antes de que la persona llegue al computador | Hito 2 |
| Correo | Opcional | Posterior |

`monitor probar-aviso` envía un mensaje de prueba por cada canal. Si un canal falla, se intentan los demás y el fallo queda registrado.

### 4.6 Otros comandos

| Comando | Función |
|---|---|
| `monitor estado` | Muestra el estado, la última consulta y los últimos resultados |
| `monitor reanudar` | Quita la pausa y reinicia el contador de errores |
| `monitor diagnostico` | Ejecuta **una vez**, solo lectura, las combinaciones de Devoluciones (Videoatención y Presencial) y un control con RUT. Si el control falla, el flujo está roto y no se puede concluir nada sobre Devoluciones |

### 4.7 Frecuencia

- Una consulta por hora, con un retraso aleatorio de 0 a 5 minutos.
- `config.toml` rechaza intervalos menores de 60 minutos para la programación.
- Un archivo de bloqueo impide dos ejecuciones simultáneas.
- Ventana horaria configurable, sin consultas desde la 01:00 hasta las 05:00 de forma predeterminada. Es solo un valor inicial: desactívela si el historial o la DIAN indican que los cupos se publican de madrugada.

### 4.8 Datos y privacidad

- Los datos personales (tipo y número de documento, nombre, correo, teléfono) se guardan **solo** en `.env`, que no se versiona.
- En sistemas Unix, `.env` debe tener permisos `600`. En Windows, conviene restringir el acceso a la cuenta de la persona usuaria.
- Los datos se usan solo en el comando `reservar`, nunca en la consulta horaria.
- El historial y los registros no deben contener datos personales. Las capturas se toman únicamente durante `consultar`, que no maneja esos datos.
- Los datos se envían solo al sitio de la DIAN. Los avisos de Telegram no incluyen datos personales.

### 4.9 Configuración de ejemplo

`config.toml`

```toml
[busqueda]
persona = "Persona Natural"
modalidad = "Videoatención"
servicio = "Devoluciones"
tramite = ""            # vacío: solo se autoselecciona si hay uno

[reserva]
ciudad = ""             # completar tras el hito 1
sede = ""

[programacion]
intervalo_minutos = 60
retraso_maximo_minutos = 5
sin_consultas_desde = "01:00"
sin_consultas_hasta = "05:00"
zona_horaria = "America/Bogota"

[flujo]
tiempo_maximo_paso_segundos = 60
errores_para_avisar = 3
```

`.env.ejemplo`

```dotenv
DIAN_TIPO_DOCUMENTO=
DIAN_NUMERO_DOCUMENTO=
DIAN_NOMBRES=
DIAN_APELLIDOS=
DIAN_CORREO=
DIAN_TELEFONO=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Los campos del formulario son provisionales: se ajustarán al formulario real en el hito 1.

---

## 5. Programación según el sistema operativo

| Sistema | Mecanismo | Nota |
|---|---|---|
| macOS | `launchd` (LaunchAgent con `StartInterval=3600`) | Debe ser un agente de la sesión del usuario para que se puedan abrir ventanas |
| Linux | temporizador de `systemd --user` o `cron` | Definir `DISPLAY` y `DBUS_SESSION_BUS_ADDRESS` para poder abrir ventanas y enviar avisos |
| Windows | Programador de tareas | Usar «Ejecutar solo cuando el usuario haya iniciado sesión» para que el navegador sea visible |

**Requisitos para el otro computador**

- Debe permanecer encendido, sin suspenderse y con la sesión iniciada.
- Una consulta perdida por suspensión no debe generar una ráfaga al despertar. Se ejecuta como máximo una.
- Si se usa un servidor sin pantalla, `consultar` y los avisos funcionarán, pero `reservar` necesitará otra solución, como escritorio remoto. Esto debe decidirse antes de instalar (sección 8).

---

## 6. Plan de construcción

### Hito 1: exploración y consulta básica

- Crear el proyecto e instalar Playwright.
- Implementar el flujo y `clasificador.py`.
- Implementar `monitor diagnostico` y ejecutarlo una vez.
- Con un servicio que sí avance, documentar los pasos siguientes hasta el captcha, **sin enviar datos ni confirmar nada**. Ampliar la sección 2.1 con lo aprendido.

**Listo cuando:** el diagnóstico clasifica correctamente Devoluciones y el control con RUT.

### Hito 2: estado, historial y avisos

- Implementar el estado, el historial, los contadores de errores y el bloqueo.
- Implementar los avisos y `probar-aviso`.

**Listo cuando:** los avisos llegan por cada canal y un fallo provocado termina en aviso tras 3 errores.

### Hito 3: reserva asistida

- Implementar `monitor reservar` hasta el captcha.
- Probarlo con el control de RUT, **deteniéndose antes de enviar cualquier formulario**.

**Listo cuando:** la herramienta llega hasta el captcha y, al resolverlo, rellena el documento sin confirmar. Esta prueba manual no debe enviar el formulario.

### Hito 4: programación y mejora

- Crear las plantillas de programación y el README de instalación.
- Instalar en el otro computador y dejarlo funcionando 24 horas.
- Si se conoce el paso de cupos, ampliar `consultar` para detectar `SIN_CUPOS` por separado.

**Listo cuando:** el historial muestra unas 19 a 24 consultas en 24 horas, según la ventana horaria, sin consultas duplicadas.

---

## 7. Pruebas

**Automáticas, sin acceso al sitio**

- Clasificador con las respuestas de la sección 2.1, incluida la doble decodificación de `d`.
- Respuestas malformadas o con valores desconocidos dan `RESPUESTA_DESCONOCIDA`.
- El estado `PAUSADO` impide consultar.
- El tercer error seguido avisa, y una consulta correcta reinicia el contador.
- Los intervalos menores de 60 minutos se rechazan.
- El historial y los registros no contienen los valores de `.env`.

**Manuales, contra el sitio real, con pocas ejecuciones**

- `monitor diagnostico` da los resultados esperados.
- `monitor reservar` con el control de RUT llega hasta el captcha y **no** confirma.
- Un cambio simulado del selector produce `ERROR_FLUJO` y una captura.

**Criterios de aceptación**

1. Con la situación del 2026-11-05, el resultado es `SIN_SERVICIO` y no se envía ningún aviso.
2. Una respuesta positiva produce un único aviso y deja de consultar hasta usar `reanudar`.
3. Un cambio en el sitio se manifiesta como error, nunca como «sin citas».
4. Ningún comando pulsa la confirmación final ni interactúa con el captcha.
5. Ningún dato personal queda fuera de `.env`.

---

## 8. Decisiones pendientes

Conviene resolverlas antes o durante el hito 1:

1. **Sistema operativo y tipo de equipo:** ¿tendrá pantalla y sesión iniciada? Si es un servidor sin pantalla, hay que definir cómo se hará la reserva.
2. **Canal de aviso al celular:** el documento propone Telegram.
3. **Ciudad y sede preferidas**, si el flujo las pide en videoatención.
4. **Trámite específico** dentro de Devoluciones, si aparecen varios.
5. **Confirmación con la DIAN** de que Devoluciones se ofrece por videoatención.

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Devoluciones por videoatención no existe y nunca aparecerá | Llamar al Contact Center y ejecutar `diagnostico` |
| La cita se ocupa antes de que la persona llegue | Aviso al celular y flujo avanzado de antemano |
| El sitio cambia y el monitor falla sin que nadie lo note | Errores separados de «sin citas» y aviso tras 3 fallos |
| El servicio aparece, pero sin fechas libres | Aviso que distingue «hay trámite» de «hay cita», y `reanudar` |
| El sitio limita o bloquea el acceso automatizado | Una consulta por hora; ante un bloqueo, **parar y avisar**, sin intentar evadirlo |
| El computador se suspende | Configuración de energía y revisión de `monitor estado` |

---

## 10. Inicio rápido en el otro computador

```bash
mkdir monitor-citas-dian
```

```bash
cd monitor-citas-dian
```

Copie este archivo a esa carpeta y, si usa Claude Code, ábrala allí y pida:

> Lee ESPECIFICACION-monitor-citas-dian.md y construye el hito 1. Antes de empezar, hazme las preguntas de la sección 8 que afecten a este hito.
