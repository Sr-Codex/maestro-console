# maestro console 🎼

Orquestrador de **agentes de IA em terminal**, *terminal-first*, para handhelds Linux ARM
(ClockworkPi uConsole / Raspberry Pi CM4). Inspirado no [Maestri](https://www.themaestri.app),
reproduz **o que importa** — orquestração e handoff entre agentes — sem o peso do canvas gráfico.

> Estado: **em desenvolvimento inicial** (Épico 1 / fundação). Veja o planejamento em
> `_bmad-output/planning-artifacts/` (local).

## Como funciona (resumo)

- Um **orquestrador** delega tarefas a agentes de codificação (Claude Code, Codex, …), **extrai**
  a resposta e **encaminha** ao próximo (fluxo orquestrador-mediado).
- **Caminho de dados = headless** (`claude -p`, `codex exec`): saída limpa, fim por *exit code*.
- **Caminho de visibilidade = tmux** (log da execução headless) — opcional.
- Mensagens entre agentes via **envelope JSON estrito** (`DONE/BLOCKED/FAILED/NEEDS_INPUT`).

## Requisitos

- **Linux aarch64** (testado em Kali no uConsole/CM4)
- **Python 3.11+**
- **tmux 3.2+**
- **CLIs dos agentes instalados e autenticados**: `claude` e/ou `codex` (dependem de API/rede)

## Instalação (manual)

```bash
git clone <repo> maestri-console
cd maestri-console
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"      # núcleo + ferramentas de teste/lint
# opcional: pip install -e ".[tui]"   # interface TUI (Épico 4)
```

## Testes

```bash
pytest
```

## Licença

[MIT](LICENSE).
