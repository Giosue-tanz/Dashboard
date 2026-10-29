#!/usr/bin/env bash
# Installa Dashboard per l'utente corrente: voce di menu e icona sul Desktop.
# Non tocca i dati personali.
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
APPS="$HOME/.local/share/applications"
DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
DATI="${XDG_DATA_HOME:-$HOME/.local/share}/Vita"

chmod +x "$REPO/avvia.sh" "$REPO/aggiorna.sh" "$REPO/main.py" 2>/dev/null || true
mkdir -p "$APPS" "$DATI"

VOCE="$APPS/dashboard.desktop"
cat > "$VOCE" <<DESKTOPFILE
[Desktop Entry]
Type=Application
Version=1.0
Name=Dashboard
GenericName=Diario e quadro personale
Comment=Emozioni, salute, carriera, studio e finanza — tutto offline
Exec=$REPO/avvia.sh
Path=$REPO
Icon=$REPO/risorse/icona.png
Terminal=false
Categories=Office;Utility;
Keywords=diario;umore;emozioni;salute;abitudini;studio;progetti;
StartupNotify=true
StartupWMClass=main.py
DESKTOPFILE
chmod +x "$VOCE"

if [ -d "$DESKTOP" ]; then
    rm -f "$DESKTOP/Vita.desktop"          # vecchio nome, se c'è ancora
    cp "$VOCE" "$DESKTOP/Dashboard.desktop"
    chmod +x "$DESKTOP/Dashboard.desktop"
    gio set "$DESKTOP/Dashboard.desktop" metadata::trusted true 2>/dev/null || true
fi

update-desktop-database "$APPS" 2>/dev/null || true
kbuildsycoca6 --noincremental >/dev/null 2>&1 || true

echo "Dashboard installata."
echo "  codice:  $REPO"
echo "  dati:    $DATI   (non vengono mai sovrascritti dagli aggiornamenti)"
echo "  avvio:   icona sul Desktop, menu applicazioni, oppure $REPO/avvia.sh"
