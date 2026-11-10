#!/usr/bin/env bash
# Instalacja per-user, bez sudo i bez modyfikowania globalnego systemu.
set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="${HOME}/.local/share/pomocnik-github"
BIN_HOME="${HOME}/.local/bin"
APPS_HOME="${HOME}/.local/share/applications"
ICONS_HOME="${HOME}/.local/share/icons/hicolor/scalable/apps"

# Wykryj rodzinę systemu, aby nie podpowiadać poleceń dnf na Kubuntu/Ubuntu.
OS_ID=""
OS_LIKE=""
OS_PRETTY="Linux"
if [[ -r /etc/os-release ]]; then
  # /etc/os-release zawiera standardowe pola ID / ID_LIKE / PRETTY_NAME.
  source /etc/os-release
  OS_ID="${ID:-}"
  OS_LIKE="${ID_LIKE:-}"
  OS_PRETTY="${PRETTY_NAME:-Linux}"
fi
if [[ " ${OS_ID} ${OS_LIKE} " == *ubuntu* || " ${OS_ID} ${OS_LIKE} " == *debian* ]]; then
  INSTALL_HINT='sudo apt install git python3 python3-tk'
elif [[ " ${OS_ID} ${OS_LIKE} " == *fedora* || " ${OS_ID} ${OS_LIKE} " == *rhel* ]]; then
  INSTALL_HINT='sudo dnf install git python3 python3-tkinter'
elif command -v apt >/dev/null 2>&1; then
  INSTALL_HINT='sudo apt install git python3 python3-tk'
elif command -v dnf >/dev/null 2>&1; then
  INSTALL_HINT='sudo dnf install git python3 python3-tkinter'
else
  INSTALL_HINT='zainstaluj git, Python 3 i tkinter w menedżerze pakietów swojego systemu'
fi

if ! command -v git >/dev/null 2>&1; then
  printf 'Brakuje programu Git. Wymagane pakiety: %s\n' "$INSTALL_HINT" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'Brakuje Pythona 3. Wymagane pakiety: %s\n' "$INSTALL_HINT" >&2
  exit 1
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  printf 'Brakuje modułu tkinter. Na tym systemie użyj: %s\n' "$INSTALL_HINT" >&2
  exit 1
fi

mkdir -p -- "$APP_HOME" "$BIN_HOME" "$APPS_HOME" "$ICONS_HOME"
install -m 644 -- "$HERE/pomocnik_github.py" "$APP_HOME/pomocnik_github.py"
install -m 755 -- "$HERE/git_askpass.py" "$APP_HOME/git_askpass.py"
install -m 644 -- "$HERE/pomocnik-github.svg" "$ICONS_HOME/pomocnik-github.svg"

cat > "$BIN_HOME/pomocnik-github" <<EOF
#!/usr/bin/env bash
exec python3 "${APP_HOME}/pomocnik_github.py" "\$@"
EOF
chmod 755 "$BIN_HOME/pomocnik-github"

cat > "$APPS_HOME/pomocnik-github.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Pomocnik GitHub
GenericName=Zarządzanie projektami GitHub
Comment=Pobierz, wyślij i synchronizuj projekty z GitHubem, otwórz w Kate
Exec=${BIN_HOME}/pomocnik-github
Icon=${ICONS_HOME}/pomocnik-github.svg
Terminal=false
Categories=Development;Utility;
Keywords=Git;GitHub;Kate;FreeCAD;Projekty;Kubuntu;Ubuntu;
StartupNotify=true
EOF
chmod 644 "$APPS_HOME/pomocnik-github.desktop"

printf '\nGOTOWE! Pomocnik GitHub 1.1 jest zainstalowany dla użytkownika %s.\n' "${USER:-użytkownik}"
printf 'System: %s\n' "$OS_PRETTY"
printf 'Uruchom z menu aplikacji KDE: Pomocnik GitHub.\n'
printf 'Nie wymaga sudo ani stałego otwartego terminala.\n'
