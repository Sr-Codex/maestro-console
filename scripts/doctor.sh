#!/usr/bin/env bash
# maestro console — doctor: verifica a prontidão do ambiente (E5-S2).
# Uso: bash scripts/doctor.sh   (rode dentro do venv para checar o pacote)
set -u
fail=0

echo "== maestro console — doctor =="
echo "- python: $(python3 --version 2>&1)"

check() {  # check <cmd> <req|opt>
  if command -v "$1" >/dev/null 2>&1; then
    echo "  ok   $1 ($($1 --version 2>&1 | head -1))"
  else
    echo "  MISS $1"
    [ "$2" = "req" ] && fail=1
  fi
}

echo "- ferramentas:"
check tmux req
check bwrap req
check claude opt
check codex opt

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
