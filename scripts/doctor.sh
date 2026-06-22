#!/usr/bin/env bash
# maestro console — doctor: verifica a prontidão do ambiente.
# Uso: bash scripts/doctor.sh   (rode dentro do venv para checar o pacote)
set -u
fail=0

echo "== maestro console — doctor =="
echo "- python: $(python3 --version 2>&1)"

check() {  # check <cmd> <req|opt> [nota]
  if command -v "$1" >/dev/null 2>&1; then
    echo "  ok   $1 ($($1 --version 2>&1 | head -1))"
  else
    echo "  MISS $1${3:+  ($3)}"
    [ "$2" = "req" ] && fail=1
  fi
}

pycheck() {  # pycheck "<descrição>" "<código python>" <req|opt> [nota]
  if python3 -c "$2" >/dev/null 2>&1; then
    echo "  ok   $1"
  else
    echo "  MISS $1${4:+  ($4)}"
    [ "$3" = "req" ] && fail=1
  fi
}

echo "- ferramentas (requisito):"
check tmux req "observabilidade da TUI"
check bwrap req "sandbox dos agentes (ADR-6)"
check git req "floors (git worktree)"

echo "- agentes (opcional — ao menos um p/ uso real):"
check claude opt
check codex opt

echo "- canvas nativo (opcional — GTK na tela do dispositivo):"
pycheck "PyGObject (gi)" "import gi" opt "apt: python3-gi"
pycheck "GTK 3.0" "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" opt "apt: gir1.2-gtk-3.0"
pycheck "VTE 2.91" "import gi; gi.require_version('Vte','2.91'); from gi.repository import Vte" opt "apt: gir1.2-vte-2.91"
check notify-send opt "notificações de desktop (attention)"

echo "- pacote:"
if python3 -c "import maestro; print('  ok   maestro', maestro.__version__)" 2>/dev/null; then :; else
  echo "  MISS maestro (rode 'pip install -e .' no venv)"; fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "RESULTADO: PRONTO ✅"
else
  echo "RESULTADO: NÃO PRONTO ❌ (instale os itens 'MISS' marcados como requisito)"
fi
exit "$fail"
