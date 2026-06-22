"""TUI app — loop de terminal sobre o TUIController (V2-S4 / FR11).

Cria e executa cadeias multiagente SEM escrever scripts: escolher um Team ou
montar uma cadeia (agentes+ordem), executar com progresso por etapa, ver o
resultado final e **cancelar com Ctrl-C** (cancelamento seguro). Render fino;
lógica no controller (testado).
"""

from __future__ import annotations

import asyncio

from ..engine.teams import Role, Team
from .controller import TUIController

MENU = """
maestro console 🎼
  [1] dashboard
  [2] rodar time
  [3] montar cadeia (agentes+ordem)
  [4] delegar tarefa (1 agente)
  [5] histórico
  [6] gerenciar teams
  [7] retomar cadeia escalada
  [q] sair
> """


def _retomar(controller: TUIController) -> None:  # pragma: no cover - input
    if not controller.can_resume():
        print("não há cadeia escalada para retomar")
        return
    print("opções: [enter] retomar igual · [a]gente trocar · [r]eprompt")
    op = input("> ").strip().lower()
    swap = reprompt = None
    if op == "a":
        swap = input("  novo agente: ").strip() or None
    elif op == "r":
        reprompt = input("  instrução extra: ").strip() or None
    try:
        res = asyncio.run(controller.resume_last(swap_agent=swap, reprompt=reprompt))
    except KeyboardInterrupt:
        print("⛔ cancelado com segurança")
        return
    if res.ok:
        print(f"✅ retomada concluída: {res.envelopes[-1].result}")
    else:
        print(f"⚠️ ainda escalou: {res.reason}")


def _coletar_roles() -> list[tuple[str, str, str]]:  # pragma: no cover - input
    roles = []
    print("papéis (em ordem; papel vazio encerra):")
    while True:
        nome = input("  papel: ").strip()
        if not nome:
            break
        agente = input("  agente: ").strip()
        instr = input("  instrução curta: ").strip()
        roles.append((nome, agente, instr))
    return roles


def _gerenciar_teams(controller: TUIController) -> None:  # pragma: no cover - input
    while True:
        print("teams:", ", ".join(controller.list_teams()))
        op = (
            input("  [l]istar [c]riar [e]ditar [d]uplicar [x]excluir [v]er [b]voltar > ")
            .strip()
            .lower()
        )
        if op == "b" or op == "":
            return
        if op == "l":
            print("\n".join(controller.list_teams()))
        elif op == "v":
            print(controller.team_detail_text(input("  nome: ").strip()))
        elif op in ("c", "e"):
            nome = input("  nome do team: ").strip()
            roles = _coletar_roles()
            try:
                t = controller.save_team(nome, roles)
                print(f"  ✓ salvo: {t.route}")
            except Exception as e:
                print(f"  ✗ inválido: {e}")
        elif op == "d":
            src = input("  origem: ").strip()
            novo = input("  novo nome: ").strip()
            try:
                controller.duplicate_team(src, novo)
                print("  ✓ duplicado")
            except Exception as e:
                print(f"  ✗ {e}")
        elif op == "x":
            nome = input("  excluir qual: ").strip()
            if input(f"  confirmar exclusão de {nome!r}? (s/N) ").strip().lower() == "s":
                controller.delete_team(nome)
                print("  ✓ excluído")
            else:
                print("  cancelado")


async def _live(controller: TUIController, team: Team, intent: str):  # pragma: no cover
    """Roda a cadeia e redesenha o dashboard ao vivo (~1s) até terminar."""
    run = asyncio.create_task(controller.run_team(team, intent))
    try:
        while not run.done():
            print("\033[2J\033[H", end="")  # limpa a tela
            print(controller.dashboard_text())
            print("\n(Ctrl-C cancela)")
            await asyncio.wait({run}, timeout=1.0)
    except asyncio.CancelledError:
        run.cancel()
        raise
    return await run


def _run_chain(controller: TUIController, team: Team) -> None:  # pragma: no cover
    intent = input("intenção/tarefa: ").strip()
    try:
        res = asyncio.run(_live(controller, team, intent))
    except KeyboardInterrupt:
        print("⛔ cancelado com segurança (processos/locks/fila liberados)")
        return
    if res.ok:
        print(f"✅ final: {res.envelopes[-1].result}")
    else:
        print(f"⚠️ escalou: {res.reason} — use 'retomar' p/ recuperar do checkpoint")


def run(controller: TUIController) -> None:  # pragma: no cover - loop interativo
    while True:
        choice = input(MENU).strip().lower()
        if choice == "q":
            return
        if choice == "1":
            print(controller.dashboard_text())
        elif choice == "2":
            print("times:", ", ".join(controller.list_teams()))
            team = controller.get_team(input("time: ").strip())
            if team is None:
                print("time não encontrado")
            else:
                _run_chain(controller, team)
        elif choice == "3":
            agentes = [
                a.strip() for a in input("agentes (em ordem, vírgula): ").split(",") if a.strip()
            ]
            if not agentes:
                print("nenhum agente")
                continue
            instr = (
                input("instrução curta por etapa: ").strip() or "Faça sua parte; result objetivo."
            )
            roles = [Role(f"step{i + 1}", ag, instr) for i, ag in enumerate(agentes)]
            _run_chain(controller, Team("ad-hoc", roles))
        elif choice == "4":
            agent_id = input("agente: ").strip()
            task = input("tarefa: ").strip()
            env = asyncio.run(controller.delegate(agent_id, task))
            print(f"-> {env.state}: {env.result or env.note or ''}")
        elif choice == "5":
            print(controller.history_text())
        elif choice == "6":
            _gerenciar_teams(controller)
        elif choice == "7":
            _retomar(controller)
        else:
            print("opção inválida")
