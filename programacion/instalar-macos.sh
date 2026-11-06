#!/bin/sh
# Instala o desinstala la consulta cada hora para el usuario actual.
set -eu

ETIQUETA="com.monitor-dian.consultar"
DESTINO="$HOME/Library/LaunchAgents/$ETIQUETA.plist"
DOMINIO="gui/$(id -u)"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"

launchctl bootout "$DOMINIO/$ETIQUETA" 2>/dev/null || true

if [ "${1:-}" = "--desinstalar" ]; then
    rm -f "$DESTINO"
    echo "Consulta cada hora desinstalada."
    exit 0
fi

mkdir -p "$RAIZ/datos" "$HOME/Library/LaunchAgents"
sed "s|__RAIZ__|$RAIZ|g" "$RAIZ/programacion/$ETIQUETA.plist.plantilla" > "$DESTINO"
launchctl bootstrap "$DOMINIO" "$DESTINO"
echo "Consulta cada hora instalada: $DESTINO"
