# maestro console 🎼

Orquestrador de **agentes de IA em terminal**, *terminal-first*, para handhelds
Linux ARM (ClockworkPi uConsole / Raspberry Pi CM4). Inspirado no
[Maestri](https://www.themaestri.app), reproduz **o que importa** — orquestração
e handoff entre agentes — sem o peso de um canvas gráfico, com **isolamento de
segurança** por padrão.

> Estado: **MVP funcional**. Um orquestrador delega tarefas a múltiplos agentes
> reais (Claude Code, Codex), cada um isolado, com handoff encadeado A→B→A.

## Como funciona

- **Orquestrador-mediado**: o orquestrador chama o agente A, **extrai** a
  resposta e a **encaminha** ao agente B (não é agente↔agente direto).
- **Caminho de dados = headless** (`claude -p`, `codex exec`): saída limpa, fim
  por *exit code*. **Visibilidade** opcional via pane tmux (`tail -f` do log).
- **Mensagens** entre agentes via **envelope JSON estrito** (validado por schema;
  estados `DONE / BLOCKED / FAILED / NEEDS_INPUT`); artefatos grandes por caminho.
- **Segurança**: cada agente roda em **sandbox bwrap** — workspace rw, `/tmp`
  privado, resto do sistema read-only, rede mantida. **Sem bypass de permissões.**
- **Sessões** persistentes (`--session-id`/`--resume`) com **mutex por sessão**
  (1 tarefa ativa por agente). Estado em **SQLite (WAL)**.

## Requisitos

- **Linux aarch64** (testado em Kali no uConsole/CM4)
- **Python 3.11+**, **tmux 3.2+**, **bwrap (bubblewrap)**
- **CLIs dos agentes instalados e autenticados**: `claude` e/ou `codex`
  (dependem de **API/rede**, portanto o produto **não** é totalmente offline)

## Instalação (manual)

```bash
git clone <repo> maestri-console
cd maestri-console
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso

```bash
maestro tui        # interface de terminal (lista agentes, histórico, delegar)
maestro --version
```

Observar a execução em outro pane:

```bash
tmux attach -t maestro-observe
```

## Configuração

- `MAESTRO_AGENT_CEILING` — teto de agentes concorrentes (default 3; suba
  conforme a RAM).
- `MAESTRO_HOME` — diretório de estado (default `~/.local/share/maestro-console`).

## Desenvolvimento

```bash
pytest                                  # testes (rápidos; live são pulados)
ruff check maestro tests                # lint
MAESTRO_LIVE=1 pytest tests/test_*_live.py   # testes de integração reais (gastam tokens)
```

## Arquitetura

Engine desacoplada da UI: `runner` (headless), `session` (+mutex), `registry`,
`adapters` (perfis TOML), `envelope` (JSON), `bus`, `queue`, `orchestrator`,
`sandbox` (bwrap), `artifacts`, `state/store` (SQLite). Frontend: `tui`.
Detalhes em `_bmad-output/planning-artifacts/` (local).

## Licença

[MIT](LICENSE).
