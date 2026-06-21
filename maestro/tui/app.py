"""TUI app — loop de terminal enxuto sobre o TUIController (E4-S2 / FR11).

Interface mínima, navegável por teclado físico (sem mouse), adequada à tela do
uConsole. Render/loop é fino; toda a lógica está no controller (testado).
Textual/rich ficam como evolução futura (mantém o MVP leve).
"""

from __future__ import annotations

import asyncio

from .controller import TUIController

MENU = """
maestro console 🎼
  [1] agentes/estado
  [2] histórico de handoffs
  [3] delegar tarefa
  [q] sair
> """


def run(controller: TUIController) -> None:  # pragma: no cover - loop interativo
    while True:
        choice = input(MENU).strip().lower()
        if choice == "q":
            return
        if choice == "1":
            print(controller.agents_text())
        elif choice == "2":
            print(controller.history_text())
        elif choice == "3":
            agent_id = input("agente: ").strip()
            task = input("tarefa: ").strip()
            env = asyncio.run(controller.delegate(agent_id, task))
            print(f"-> {env.state}: {env.result or env.note or ''}")
        else:
            print("opção inválida")
