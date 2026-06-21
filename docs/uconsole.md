# maestro console no ClockworkPi uConsole (CM4)

Notas específicas do dispositivo onde o projeto foi desenvolvido e validado.

## Hardware/ambiente validado

- **ClockworkPi uConsole**, Raspberry Pi **CM4**, ARM Cortex-A72 **aarch64**
- **Kali Linux** (rolling), kernel 6.12.x, shell zsh
- ~3.7 GB RAM, **zram** como swap (~3 GB comprimido em RAM)
- Tela **1280×720**, teclado físico
- `tmux` 3.6, `bwrap`, Python 3.13, Node 24 já presentes na imagem testada

## Pré-requisitos

```bash
sudo apt update
sudo apt install -y tmux bubblewrap python3-venv
# CLIs dos agentes (autentique cada um):
#   claude  -> Claude Code
#   codex   -> OpenAI Codex
```

## Instalação

```bash
git clone <repo> maestri-console && cd maestri-console
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
bash scripts/doctor.sh        # confere prontidão do ambiente
maestro tui                   # inicia
```

## Notas de desempenho (CM4)

- **Teto de agentes**: default 3. Com a RAM atual, 4 agentes ativos ainda deixam
  ~800 MB livres **sem swap** (validado). Ajuste com `MAESTRO_AGENT_CEILING`.
  Ao **aumentar a RAM**, suba esse valor.
- O trabalho pesado dos agentes é **remoto (API)** — o uso local é sobretudo CPU
  no streaming, não RAM.

## zram / swap

Se for testar com swap desligado, **reative via serviço** (não `swapon -a`):

```bash
sudo swapoff -a
# ... teste ...
sudo systemctl restart systemd-zram-setup@zram0.service   # reativa o zram
```

## Observabilidade

Em outro pane/terminal:

```bash
tmux attach -t maestro-observe   # acompanha o log da execução
```
