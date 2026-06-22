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
pip install -e ".[web]"   # necessário para a Web UI (aiohttp)
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

## Web UI (v0.4.0)

Interface web controlável com **canvas visual** (agentes como nós, handoffs como
conexões), sobre a **mesma engine** (headless, bwrap, envelope, checkpoints).

```bash
pip install -e ".[web]"   # se ainda não instalou o extra
maestro web               # inicia o servidor
```

- **URL padrão:** http://127.0.0.1:8765
- **Host/porta:** `MAESTRO_WEB_HOST` e `MAESTRO_WEB_PORT`
  ```bash
  MAESTRO_WEB_HOST=0.0.0.0 MAESTRO_WEB_PORT=9000 maestro web
  ```

### Acesso e segurança
- **Bind padrão `127.0.0.1`** (só local). Exposição na **LAN é opt-in** (defina
  `MAESTRO_WEB_HOST=0.0.0.0`).
- Fora de localhost, um **token aleatório é obrigatório** (impresso ao iniciar) e
  enviado no **header** `X-Maestro-Token` (nunca em query string). CORS é fechado
  e o `Origin` é validado.
- **Acesso remoto seguro = SSH port forwarding** (mantém tudo em localhost, sem
  expor a LAN nem precisar de token no navegador):
  ```bash
  # na sua máquina:
  ssh -L 8765:127.0.0.1:8765 kali@<ip-do-uconsole>
  # depois abra http://127.0.0.1:8765 no navegador local
  ```

### Como usar
- **Executar um team:** escolha o team no seletor, digite a tarefa e clique
  **Executar**. O progresso de cada handoff aparece **ao vivo** (SSE).
- **Cancelar:** botão **Cancelar** (libera processo, lock e fila).
- **Retomar:** botão **Retomar** continua do último checkpoint (sem repetir
  etapas concluídas; opções de trocar agente/reprompt na TUI).
- **Canvas:** agentes são **nós** coloridos por estado (idle/busy/blocked/failed/
  done) e as rotas do team são **conexões**; **arraste os nós** para reposicionar
  (as posições são persistidas).

> ⚠️ **Rede e tokens:** os agentes **Claude Code** e **Codex** chamam suas **APIs**
> (Anthropic/OpenAI) — exigem **conexão de rede e autenticação/tokens** próprios.
> A engine roda local, mas os agentes **não** são offline.

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
