"""State Store — persistência segura em SQLite (WAL). E1-S3 / ADR-9.

Única camada de acesso ao estado (sessões, tarefas, log de envelopes).
Proibida escrita JSON concorrente direta: aqui tudo passa por transações
SQLite, com WAL para leitura concorrente e um lock que serializa escritores
("escritor único" lógico).

Não conhece envelope/adapter — só persiste dados primitivos/JSON.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    agent_id   TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    intent      TEXT,
    target      TEXT,
    status      TEXT NOT NULL,
    result_json TEXT,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS envelope_log (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    task_id    TEXT,
    sender     TEXT,
    recipient  TEXT,
    state      TEXT,
    payload    TEXT,
    ts         REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS agents (
    id         TEXT PRIMARY KEY,
    type       TEXT NOT NULL,
    state      TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS teams (
    name       TEXT PRIMARY KEY,
    roles_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chain_runs (
    run_id     TEXT PRIMARY KEY,
    team       TEXT,
    intent     TEXT,
    status     TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chain_steps (
    run_id  TEXT NOT NULL,
    idx     INTEGER NOT NULL,
    role    TEXT,
    agent   TEXT,
    state   TEXT,
    result  TEXT,
    PRIMARY KEY (run_id, idx)
);
CREATE TABLE IF NOT EXISTS node_positions (
    agent_id TEXT PRIMARY KEY,
    x        REAL NOT NULL,
    y        REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ui_state (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    src        TEXT NOT NULL,
    dst        TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (src, dst)
);
CREATE TABLE IF NOT EXISTS floors (
    name        TEXT PRIMARY KEY,
    branch      TEXT NOT NULL,
    path        TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS floor_hooks (
    name     TEXT PRIMARY KEY,
    setup    TEXT,
    run      TEXT,
    teardown TEXT
);
CREATE TABLE IF NOT EXISTS notes (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    x          REAL NOT NULL,
    y          REAL NOT NULL,
    updated_at REAL NOT NULL,
    color      TEXT NOT NULL DEFAULT '',
    pinned     INTEGER NOT NULL DEFAULT 0,
    font       TEXT NOT NULL DEFAULT '',
    width      REAL NOT NULL DEFAULT 200,
    height     REAL NOT NULL DEFAULT 110
);
CREATE TABLE IF NOT EXISTS routines (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    agent      TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    interval_s REAL NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1,
    run_count  INTEGER NOT NULL DEFAULT 0,
    last_run   REAL
);
CREATE TABLE IF NOT EXISTS groups (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    color      TEXT NOT NULL,
    x          REAL NOT NULL,
    y          REAL NOT NULL,
    w          REAL NOT NULL,
    h          REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


class Store:
    """Acesso transacional ao estado (SQLite WAL). Thread-safe."""

    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL: leitores concorrentes + um escritor; busy_timeout evita "locked".
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        with self._conn:
            self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Migrações idempotentes (sem framework): ALTER TABLE p/ DBs antigos. Cada
        coluna nova é adicionada se ainda não existir (OperationalError = já existe)."""
        alters = (
            "ALTER TABLE notes ADD COLUMN color TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE notes ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE notes ADD COLUMN font TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE notes ADD COLUMN width REAL NOT NULL DEFAULT 200",
            "ALTER TABLE notes ADD COLUMN height REAL NOT NULL DEFAULT 110",
        )
        for ddl in alters:
            try:
                with self._conn:
                    self._conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # coluna já existe (DB já migrado)

    # -- backup / restore (V11-S3) -------------------------------------
    _BACKUP_TABLES = (
        "sessions",
        "tasks",
        "envelope_log",
        "agents",
        "teams",
        "chain_runs",
        "chain_steps",
        "node_positions",
        "ui_state",
        "edges",
        "floors",
        "floor_hooks",
        "notes",
        "routines",
        "groups",
    )

    def export_all(self) -> dict[str, list[dict[str, Any]]]:
        """Snapshot de todas as tabelas (dict tabela -> linhas)."""
        out: dict[str, list[dict[str, Any]]] = {}
        with self._lock:
            for t in self._BACKUP_TABLES:
                rows = self._conn.execute(f"SELECT * FROM {t}").fetchall()  # noqa: S608 (nome fixo)
                out[t] = [dict(r) for r in rows]
        return out

    def import_all(self, data: dict[str, list[dict[str, Any]]], *, replace: bool = True) -> None:
        """Restaura o estado. replace=True limpa cada tabela presente antes de inserir."""
        with self._lock, self._conn:
            for t in self._BACKUP_TABLES:
                rows = data.get(t)
                if rows is None:
                    continue
                if replace:
                    self._conn.execute(f"DELETE FROM {t}")  # noqa: S608 (nome fixo)
                for row in rows:
                    cols = list(row.keys())
                    placeholders = ",".join("?" * len(cols))
                    colnames = ",".join(cols)
                    self._conn.execute(
                        f"INSERT OR REPLACE INTO {t}({colnames}) VALUES({placeholders})",  # noqa: S608
                        [row[c] for c in cols],
                    )

    # -- infraestrutura -------------------------------------------------
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def journal_mode(self) -> str:
        with self._lock:
            return self._conn.execute("PRAGMA journal_mode;").fetchone()[0]

    # -- sessões (FR13) -------------------------------------------------
    def set_session(self, agent_id: str, session_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions(agent_id, session_id, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(agent_id) DO UPDATE SET session_id=excluded.session_id, "
                "updated_at=excluded.updated_at",
                (agent_id, session_id, time.time()),
            )

    def delete_session(self, agent_id: str) -> None:
        """Apaga a sessão do agente (troca de CONTA — docs/31 E3: a sessão antiga vive
        no config-dir antigo; um --resume dela sob a conta nova falharia)."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM sessions WHERE agent_id=?", (agent_id,))

    def get_session(self, agent_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT session_id FROM sessions WHERE agent_id=?", (agent_id,)
            ).fetchone()
        return row["session_id"] if row else None

    # -- tarefas --------------------------------------------------------
    def create_task(
        self,
        task_id: str,
        intent: str | None = None,
        target: str | None = None,
        status: str = "queued",
    ) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO tasks(id,intent,target,status,attempts,created_at,updated_at) "
                "VALUES(?,?,?,?,0,?,?)",
                (task_id, intent, target, status, now, now),
            )

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        result: Any | None = None,
        bump_attempts: bool = False,
    ) -> None:
        sets: list[str] = ["updated_at=?"]
        params: list[Any] = [time.time()]
        if status is not None:
            sets.append("status=?")
            params.append(status)
        if result is not None:
            sets.append("result_json=?")
            params.append(json.dumps(result))
        if bump_attempts:
            sets.append("attempts=attempts+1")
        params.append(task_id)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", params)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["result"] = json.loads(d["result_json"]) if d["result_json"] else None
        return d

    def count_tasks(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    # -- log de envelopes (FR12) ---------------------------------------
    def log_envelope(
        self,
        *,
        message_id: str,
        task_id: str | None,
        sender: str | None,
        recipient: str | None,
        state: str | None,
        payload: Any | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO envelope_log(message_id,task_id,sender,recipient,state,payload,ts) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    message_id,
                    task_id,
                    sender,
                    recipient,
                    state,
                    json.dumps(payload) if payload is not None else None,
                    time.time(),
                ),
            )

    def count_envelopes(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM envelope_log").fetchone()[0]

    def list_envelopes(self, limit: int = 50) -> list[dict[str, Any]]:
        """Últimos envelopes logados (mais recentes primeiro)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM envelope_log ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -- agentes (E1-S4) -----------------------------------------------
    def upsert_agent(self, agent_id: str, agent_type: str, state: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO agents(id, type, state, updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET type=excluded.type, state=excluded.state, "
                "updated_at=excluded.updated_at",
                (agent_id, agent_type, state, time.time()),
            )

    def set_agent_state(self, agent_id: str, state: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE agents SET state=?, updated_at=? WHERE id=?",
                (state, time.time(), agent_id),
            )

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        return dict(row) if row else None

    def list_agents(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM agents ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def remove_agent(self, agent_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))

    # -- teams (V2-S1) --------------------------------------------------
    def save_team(self, name: str, roles: list[dict[str, Any]]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO teams(name, roles_json, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET roles_json=excluded.roles_json, "
                "updated_at=excluded.updated_at",
                (name, json.dumps(roles), time.time()),
            )

    def get_team(self, name: str) -> list[dict[str, Any]] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT roles_json FROM teams WHERE name=?", (name,)
            ).fetchone()
        return json.loads(row["roles_json"]) if row else None

    def list_teams(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT name FROM teams ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    def delete_team(self, name: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM teams WHERE name=?", (name,))

    # -- checkpoints de cadeia (V3-S3) ---------------------------------
    def start_chain(self, run_id: str, team: str | None, intent: str | None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO chain_runs(run_id, team, intent, status, updated_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET "
                "team=excluded.team, intent=excluded.intent, updated_at=excluded.updated_at",
                (run_id, team, intent, "running", time.time()),
            )

    def set_chain_status(self, run_id: str, status: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE chain_runs SET status=?, updated_at=? WHERE run_id=?",
                (status, time.time(), run_id),
            )

    def save_step(
        self,
        run_id: str,
        idx: int,
        role: str,
        agent: str,
        state: str | None,
        result: str | None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO chain_steps(run_id, idx, role, agent, state, result) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(run_id, idx) DO UPDATE SET "
                "role=excluded.role, agent=excluded.agent, state=excluded.state, "
                "result=excluded.result",
                (run_id, idx, role, agent, state, result),
            )

    def get_steps(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM chain_steps WHERE run_id=? ORDER BY idx", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_chain(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM chain_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_chains(self, status: str) -> list[dict[str, Any]]:
        """Chains num dado status, mais antiga primeiro (docs/29 §4.4: a lista de retidas
        `escalated_budget` que o diálogo Limites mostra pra retomar/descartar)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM chain_runs WHERE status=? ORDER BY updated_at", (status,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -- posições dos nós no canvas (V4-S5) ----------------------------
    def set_node_position(self, agent_id: str, x: float, y: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO node_positions(agent_id, x, y) VALUES(?,?,?) "
                "ON CONFLICT(agent_id) DO UPDATE SET x=excluded.x, y=excluded.y",
                (agent_id, x, y),
            )

    def get_node_positions(self) -> dict[str, dict[str, float]]:
        with self._lock:
            rows = self._conn.execute("SELECT agent_id, x, y FROM node_positions").fetchall()
        return {r["agent_id"]: {"x": r["x"], "y": r["y"]} for r in rows}

    # -- cabos entre nós do canvas (V7-S1) -----------------------------
    def add_edge(self, src: str, dst: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO edges(src, dst, created_at) VALUES(?,?,?) "
                "ON CONFLICT(src, dst) DO NOTHING",
                (src, dst, time.time()),
            )

    def remove_edge(self, src: str, dst: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM edges WHERE src=? AND dst=?", (src, dst))

    def get_edges(self) -> list[tuple[str, str]]:
        with self._lock:
            rows = self._conn.execute("SELECT src, dst FROM edges ORDER BY created_at").fetchall()
        return [(r["src"], r["dst"]) for r in rows]

    # -- floors (ambientes isolados / git worktree) (V8-S1) ------------
    def add_floor(self, name: str, branch: str, path: str, base_branch: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO floors(name, branch, path, base_branch, created_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET "
                "branch=excluded.branch, path=excluded.path, base_branch=excluded.base_branch",
                (name, branch, path, base_branch, time.time()),
            )

    def get_floor(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM floors WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def list_floors(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM floors ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def remove_floor(self, name: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM floors WHERE name=?", (name,))
            self._conn.execute("DELETE FROM floor_hooks WHERE name=?", (name,))

    def set_floor_hooks(
        self, name: str, *, setup: str | None, run: str | None, teardown: str | None
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO floor_hooks(name, setup, run, teardown) VALUES(?,?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET setup=excluded.setup, run=excluded.run, "
                "teardown=excluded.teardown",
                (name, setup, run, teardown),
            )

    def get_floor_hooks(self, name: str) -> dict[str, str | None] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT setup, run, teardown FROM floor_hooks WHERE name=?", (name,)
            ).fetchone()
        if row is None:
            return None
        return {"setup": row["setup"], "run": row["run"], "teardown": row["teardown"]}

    # -- notas no canvas (V9-S2) ---------------------------------------
    def upsert_note(
        self,
        note_id: str,
        title: str,
        body: str,
        x: float,
        y: float,
        color: str = "",
        pinned: int = 0,
        font: str = "",
        width: float = 200.0,
        height: float = 110.0,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO notes(id, title, body, x, y, updated_at, color, pinned, font, "
                "width, height) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, body=excluded.body, "
                "x=excluded.x, y=excluded.y, updated_at=excluded.updated_at, "
                "color=excluded.color, pinned=excluded.pinned, font=excluded.font, "
                "width=excluded.width, height=excluded.height",
                (note_id, title, body, x, y, time.time(), color, int(pinned), font, width, height),
            )

    def get_note(self, note_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return dict(row) if row else None

    def list_notes(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM notes ORDER BY updated_at").fetchall()
        return [dict(r) for r in rows]

    def remove_note(self, note_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM notes WHERE id=?", (note_id,))

    # -- grupos/áreas no canvas (C2) -----------------------------------
    def upsert_group(
        self, group_id: str, title: str, color: str, x: float, y: float, w: float, h: float
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO groups(id, title, color, x, y, w, h, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, color=excluded.color, "
                "x=excluded.x, y=excluded.y, w=excluded.w, h=excluded.h, "
                "updated_at=excluded.updated_at",
                (group_id, title, color, x, y, w, h, time.time()),
            )

    def get_group(self, group_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()
        return dict(row) if row else None

    def list_groups(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM groups ORDER BY updated_at").fetchall()
        return [dict(r) for r in rows]

    def remove_group(self, group_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM groups WHERE id=?", (group_id,))

    # -- routines (prompts agendados) (V10-S1) -------------------------
    def upsert_routine(
        self,
        routine_id: str,
        name: str,
        agent: str,
        steps_json: str,
        interval_s: float,
        enabled: bool,
        run_count: int,
        last_run: float | None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO routines(id,name,agent,steps_json,interval_s,enabled,run_count,"
                "last_run) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "name=excluded.name, agent=excluded.agent, steps_json=excluded.steps_json, "
                "interval_s=excluded.interval_s, enabled=excluded.enabled, "
                "run_count=excluded.run_count, last_run=excluded.last_run",
                (
                    routine_id,
                    name,
                    agent,
                    steps_json,
                    interval_s,
                    1 if enabled else 0,
                    run_count,
                    last_run,
                ),
            )

    def get_routine(self, routine_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM routines WHERE id=?", (routine_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_routines(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM routines ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def remove_routine(self, routine_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM routines WHERE id=?", (routine_id,))

    # -- estado de UI genérico (V5-S3: viewport do canvas) -------------
    def set_ui(self, key: str, value: Any) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO ui_state(k, v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, json.dumps(value)),
            )

    def get_ui(self, key: str) -> Any | None:
        with self._lock:
            row = self._conn.execute("SELECT v FROM ui_state WHERE k=?", (key,)).fetchone()
        return json.loads(row["v"]) if row else None

    def delete_ui(self, key: str) -> None:
        """Remove a linha de ui_state (idempotente) — p/ limpar estado por-nó ao fechar."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM ui_state WHERE k=?", (key,))
