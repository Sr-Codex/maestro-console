"""Medição de RAM da ÁRVORE de processos de um nó (unload — Bloco D, docs/21 §8).

Lê ``/proc/<pid>/smaps_rollup`` (método validado ao vivo na investigação de 2026-07-03):
- **RSS** = memória vista (conta compartilhado N vezes — não usar pra somar frota);
- **PSS** = fatia real (compartilhado dividido entre quem compartilha; soma ≈ uso real);
- **Private** = exclusivo → o piso garantido a liberar ao matar o processo.

A árvore parte do filho direto do nó (o bwrap) e desce por
``/proc/<pid>/task/*/children`` (CONFIG_PROC_CHILDREN — ok no kernel 6.12 do device).
``--unshare-pid`` do sandbox NÃO esconde os filhos do host.

Contrato best-effort: PID que morreu entre o listdir e o read → contribuição parcial
silenciosa (nunca levanta). Módulo sem GTK → unit-testável no ``.venv`` contra uma
árvore REAL spawnada (provar a fonte, não parser sintético).

Custo: o rollup varre as VMAs do processo no kernel — chamar SEMPRE de um worker
thread, nunca da main loop do GTK (revisão adversarial do Fable, docs/21 §8.5).
"""

from __future__ import annotations

from pathlib import Path

_PROC = Path("/proc")

# campos do smaps_rollup que nos interessam (kB)
_FIELDS = ("Rss:", "Pss:", "Private_Clean:", "Private_Dirty:")


def tree_pids(root_pid: int, *, proc: Path = _PROC) -> list[int]:
    """PIDs da árvore inteira a partir de ``root_pid`` (inclusive), via
    ``/proc/<pid>/task/*/children``. Lista vazia se o root já morreu."""
    if not root_pid or not (proc / str(root_pid)).is_dir():
        return []
    out: list[int] = []
    stack = [int(root_pid)]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:  # defensivo (reparenting bizarro não pode virar loop)
            continue
        seen.add(pid)
        out.append(pid)
        task_dir = proc / str(pid) / "task"
        try:
            tids = list(task_dir.iterdir())
        except OSError:
            continue  # morreu no meio: contribuição parcial
        for tid in tids:
            try:
                kids = (tid / "children").read_text()
            except OSError:
                continue
            for k in kids.split():
                try:
                    stack.append(int(k))
                except ValueError:
                    continue
    return out


def _rollup_kb(pid: int, *, proc: Path = _PROC) -> tuple[int, int, int]:
    """(rss, pss, private) em kB de UM processo; (0,0,0) se morreu/inacessível."""
    vals = dict.fromkeys(_FIELDS, 0)
    try:
        text = (proc / str(pid) / "smaps_rollup").read_text()
    except OSError:
        return (0, 0, 0)
    for line in text.splitlines():
        for f in _FIELDS:
            if line.startswith(f):
                try:
                    vals[f] = int(line.split()[1])
                except (IndexError, ValueError):
                    pass
    return (vals["Rss:"], vals["Pss:"],
            vals["Private_Clean:"] + vals["Private_Dirty:"])


def tree_ram_mb(root_pid: int, *, proc: Path = _PROC) -> tuple[float, float, float]:
    """(rss, pss, private) em **MB** da árvore inteira do nó. (0,0,0) se nada vivo."""
    rss = pss = priv = 0
    for pid in tree_pids(root_pid, proc=proc):
        r, p, pv = _rollup_kb(pid, proc=proc)
        rss += r
        pss += p
        priv += pv
    return (rss / 1024, pss / 1024, priv / 1024)


def alert_step(alerted: bool, value_mb: float, limit_mb: int) -> tuple[bool, bool]:
    """Transição do alerta de RAM com HISTERESE (docs/21 §8.3-7): retorna
    ``(novo_alerted, notificar_agora)``. Notifica 1x ao cruzar o limiar; re-arma só
    quando cair abaixo de **0.9×limite** — nó oscilando em volta do limiar não vira
    spam de notificação (flapping, furo achado na revisão do Fable).

    ``limit_mb <= 0`` = desligado (nunca alerta). Puro/estático → testável no venv."""
    if limit_mb <= 0:
        return (False, False)
    if not alerted and value_mb >= limit_mb:
        return (True, True)
    if alerted and value_mb < 0.9 * limit_mb:
        return (False, False)
    return (alerted, False)


def parse_limit_mb(raw: str | None) -> int:
    """Limiar persistido (ui_state) → MB inteiro. '' / None / inválido / <=0 = 0 (off) —
    parse ruim NUNCA crasha (docs/21 §8.3-7)."""
    try:
        v = int(str(raw or "").strip())
    except ValueError:
        return 0
    return v if v > 0 else 0
