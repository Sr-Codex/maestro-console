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
