# maestro console 🎼

Orquestrador de **agentes de IA** para handhelds Linux ARM (ClockworkPi uConsole /
Raspberry Pi CM4). Um clone do [Maestri](https://www.themaestri.app) para Linux:
**canvas de terminais reais** onde agentes (Claude Code, Codex) se conectam e
passam trabalho entre si — com **isolamento de segurança** por padrão.

> Estado: **maduro**. Engine de orquestração + **3 interfaces** (TUI, Web, canvas
> nativo GTK) + cabos que conversam, ambientes isolados (floors), papéis & notas,
> rotinas agendadas e observabilidade. ~315 testes.

## O que dá pra fazer

- 🖥️ **Canvas nativo** na tela do dispositivo: terminais reais dos agentes num
  plano infinito — **pan** (arrastar o fundo ou **SELECT + trackball**), **zoom** e
  **seleção por clique** (borda azul tracejada) — confinados por sandbox.
- 🔌 **Cabos que conversam**: ligar agente A → B e disparar um **handoff**
  (A trabalha, o resultado vai para B) — mediado, registrado e recuperável.
- 🧱 **Floors**: ambientes isolados via **git worktree** (branches por agente, sem
  conflito), com hooks de ciclo de vida e **merge preview** antes de integrar.
- 👥 **Papéis & 📝 notas**: papéis com cor/badge (role.json + CLAUDE.md/AGENTS.md)
  e notas colaborativas que um agente lê e reescreve (**agent-to-note**).
- ⏰ **Routines**: prompts agendados, multi-step (`&&`), pausáveis.
- ⚠️ **Observabilidade & UX**: "o que precisa de você" (realce + notificação),
  busca rápida (**Ctrl-P**), **backup/restore** do estado, temas de terminal.

## Como funciona (princípios da engine)

- **Orquestrador-mediado**: o orquestrador chama o agente A, **extrai** a resposta
  e a **encaminha** ao B (não é agente↔agente direto). Robusto, logável, recuperável.
- **Caminho de dados = headless** (`claude -p`, `codex exec`): saída limpa, fim por
  *exit code*. O canvas/VTE é a camada **visual**; o dado segue headless.
- **Mensagens** via **envelope JSON estrito** (schema; `DONE / BLOCKED / FAILED /
  NEEDS_INPUT`); artefatos grandes por caminho.
- **Segurança**: cada agente roda em **sandbox bwrap** — workspace rw, `/tmp`
  privado, resto read-only, rede mantida. **Sem bypass de permissões.**
- **Sessões** persistentes (`--session-id`/`--resume`) com **mutex por sessão**.
  Estado em **SQLite (WAL)**.

## Requisitos

- **Linux aarch64** (testado em Kali no uConsole/CM4), **Python 3.11+**
- **Requisito:** `tmux`, `bwrap` (bubblewrap), `git`
- **Agentes:** `claude` e/ou `codex` instalados e autenticados (usam **API/rede** —
  o produto **não** é totalmente offline)
- **Canvas nativo (opcional):** PyGObject + GTK 4 + VTE-gtk4 (zoom real do plano
  infinito) — no Debian/Kali:
  `apt install python3-gi gir1.2-gtk-4.0 gir1.2-vte-3.91 libvte-2.91-gtk4-0`
- **Notificações de desktop (opcional):** `notify-send`

Verifique tudo de uma vez:

```bash
bash scripts/doctor.sh
```

## Instalação

```bash
git clone <repo> maestri-console
cd maestri-console
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[web]"   # opcional: Web UI (aiohttp)
```

> ⚠️ O **canvas nativo** usa GTK/VTE via `python3-gi`, que vive no **Python do
> sistema** (não no venv). Use o wrapper `./bin/maestro-canvas` (já chama o
> `python3` certo). Os demais comandos rodam no venv normalmente.

## Comandos

```bash
maestro tui                 # interface de terminal (dashboard, teams, delegar, retomar)
maestro web                 # Web UI (http://127.0.0.1:8765) — canvas visual + SSE
maestro canvas              # app nativo GTK+VTE na tela do dispositivo
maestro floor ...           # ambientes isolados: create/list/preview/merge/rm/run
maestro routine ...         # prompts agendados: add/list/rm/run/enable/disable/serve
maestro backup F  / restore F   # exporta/importa todo o estado (JSON)
maestro --version
```

### Canvas nativo (carro-chefe)

```bash
./bin/maestro-canvas        # abre na tela do uConsole (DISPLAY :0 por padrão)
```

- **Pan**: arraste o fundo · **Zoom**: `−`/`+` · **Mover nó**: arraste o título.
- **🔌 conectar**: clique no agente A, depois no B → cria um **cabo** (clique no
  mesmo par remove; **Esc** cancela).
- Menu **☰ ações**: rodar time · disparar handoff · nova nota · floors · routines.
- **Ctrl-P**: busca rápida (ir para um agente/team/floor/nota/routine).
- Notas têm um seletor de agente + **▶ rodar** (a nota alimenta o agente e a
  resposta volta para a nota).

### Floors (ambientes isolados)

Dentro de um repo git de projeto (ou aponte com `--project PATH` / `MAESTRO_PROJECT`):

```bash
maestro floor create exp            # cria worktree + branch floor/exp
maestro floor run exp claude "implemente X"   # roda um agente no floor (sandbox)
maestro floor preview exp           # diff + detecção de conflito (sem mexer)
maestro floor merge exp             # integra na base se não houver conflito
maestro floor rm exp                # remove worktree + branch
```

### Routines (prompts agendados)

```bash
maestro routine add ci claude "rode os testes && reporte" --interval 600
maestro routine serve               # dispara as vencidas (deixe rodando, ex.: em tmux)
maestro routine list / enable / disable / run / rm
```

> O agendamento é **in-app**: dispara enquanto `maestro routine serve` ou o canvas
> estão abertos. (Export para cron/systemd é um follow-up futuro.)

Observar a execução em outro pane:

```bash
tmux attach -t maestro-observe
```

## Web UI

Interface web controlável com **canvas visual** (agentes como nós, handoffs como
conexões), sobre a **mesma engine**.

```bash
pip install -e ".[web]"
maestro web                 # http://127.0.0.1:8765
MAESTRO_WEB_HOST=0.0.0.0 MAESTRO_WEB_PORT=9000 maestro web   # expor na LAN (opt-in)
```

- **Bind padrão `127.0.0.1`**; LAN é opt-in. Fora de localhost, um **token
  aleatório** é exigido (header `X-Maestro-Token`); CORS fechado, `Origin` validado.
- **Acesso remoto seguro = SSH port forwarding:**
  ```bash
  ssh -L 8765:127.0.0.1:8765 kali@<ip-do-uconsole>   # depois abra http://127.0.0.1:8765
  ```

## Configuração

- `MAESTRO_HOME` — diretório de estado (default `~/.local/share/maestro-console`).
- `MAESTRO_AGENT_CEILING` — teto de agentes concorrentes (default 3).
- `MAESTRO_PROJECT` — repo de projeto dos floors (override do diretório atual).
- `MAESTRO_WEB_HOST` / `MAESTRO_WEB_PORT` — bind da Web UI.

> ⚠️ **Backup/restore e hooks:** os *hooks* de floor (Setup/Run/Teardown) são
> comandos shell do usuário e rodam **fora** do sandbox. Restaure **apenas
> backups confiáveis** — um backup importado pode conter hooks.

## Desenvolvimento

```bash
.venv/bin/pytest -p no:warnings              # testes (rápidos; live são pulados)
.venv/bin/ruff check maestro tests           # lint
MAESTRO_LIVE=1 .venv/bin/pytest tests/test_*_live.py   # integração real (gasta tokens)
```

Veja o histórico de versões em [CHANGELOG.md](CHANGELOG.md).

## Arquitetura

Engine desacoplada da UI:

- **engine**: `runner` (headless), `session` (+mutex), `registry`, `adapters`
  (perfis TOML), `envelope` (JSON), `bus`, `queue`, `orchestrator`, `sandbox`
  (bwrap), `artifacts`, `state/store` (SQLite); e os módulos das fases —
  `project`/`floors`/`floor_run`/`floor_merge`/`hooks`, `roles`, `notes`,
  `routines`/`scheduler`, `attention`, `backup`.
- **interfaces**: `tui`, `web` (aiohttp+SSE), `native` (GTK+VTE).

Detalhes de planejamento em `_bmad-output/` e pesquisa em `docs/`.

## Licença

[MIT](LICENSE).
