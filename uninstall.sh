#!/usr/bin/env bash
# Usuwa tylko pliki aplikacji Pomocnik GitHub dla bieżącego użytkownika.
# Nigdy nie dotyka katalogów projektów ani repozytoriów Git.
set -Eeuo pipefail
printf 'Usunąć program Pomocnik GitHub (bez usuwania żadnych projektów)? [t/N] '
read -r answer
if [[ ! "$answer" =~ ^([tT]|[tT][aA][kK])$ ]]; then
  printf 'Anulowano.\n'
  exit 0
fi
rm -f -- "$HOME/.local/bin/pomocnik-github"
rm -f -- "$HOME/.local/share/applications/pomocnik-github.desktop"
rm -f -- "$HOME/.local/share/icons/hicolor/scalable/apps/pomocnik-github.svg"
rm -f -- "$HOME/.local/share/pomocnik-github/pomocnik_github.py"
rm -f -- "$HOME/.local/share/pomocnik-github/git_askpass.py"
rmdir -- "$HOME/.local/share/pomocnik-github" 2>/dev/null || true
printf 'Program usunięty. Twoje projekty pozostały nietknięte.\n'
