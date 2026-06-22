// maestro console — Web UI dashboard (V4-S4). Sem framework, sem build.
"use strict";

const $ = (id) => document.getElementById(id);

function hdrs(extra) {
  const h = Object.assign({ "Content-Type": "application/json" }, extra || {});
  const tok = localStorage.getItem("maestroToken");
  if (tok) h["X-Maestro-Token"] = tok; // header, nunca query string
  return h;
}
async function api(path, opts) {
  const r = await fetch(path, Object.assign({ headers: hdrs() }, opts || {}));
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status);
  return r.json();
}

async function loadAgents() {
  const agents = await api("/api/agents");
  $("agents").innerHTML = agents
    .map((a) => `<li>${a.id} [${a.type}] — <b class="st-${a.state}">${a.state}</b></li>`)
    .join("");
  if (window.MaestroCanvas) window.MaestroCanvas.setAgents(agents);
}
async function loadTeams() {
  const teams = await api("/api/teams");
  $("team").innerHTML = teams.map((t) => `<option value="${t.name}">${t.name} — ${t.route}</option>`).join("");
  window._teams = teams;
  syncCanvasRoute();
}
async function loadHistory() {
  const h = await api("/api/history?limit=15");
  $("history").textContent = h.length
    ? h.map((e) => `${e.sender} -> ${e.recipient} [${e.state || "-"}] ${e.task_id || ""}`).join("\n")
    : "(sem histórico)";
}
function syncCanvasRoute() {
  const t = (window._teams || []).find((x) => x.name === $("team").value);
  if (t && window.MaestroCanvas) window.MaestroCanvas.setRoute(t.roles.map((r) => r.agent));
}

async function refreshAll() {
  await Promise.all([loadAgents(), loadTeams(), loadHistory()]);
}

// --- execução / controle ---
$("run").onclick = async () => {
  try {
    await api("/api/execute", { method: "POST", body: JSON.stringify({ team: $("team").value, intent: $("intent").value }) });
  } catch (e) { alert("erro: " + e.message); }
};
$("cancel").onclick = () => api("/api/cancel", { method: "POST", body: "{}" }).catch(() => {});
$("resume").onclick = () =>
  api("/api/resume", { method: "POST", body: "{}" }).catch((e) => alert("retomar: " + e.message));
$("team").onchange = syncCanvasRoute;
$("token").onchange = (e) => localStorage.setItem("maestroToken", e.target.value.trim());

// --- SSE ao vivo ---
function connectSSE() {
  const es = new EventSource("/api/events");
  es.onopen = () => $("conn").classList.add("on");
  es.onerror = () => $("conn").classList.remove("on");
  es.onmessage = (ev) => {
    const e = JSON.parse(ev.data);
    if (e.type === "step") {
      const dur = e.duration_s ? ` ${e.duration_s.toFixed(1)}s` : "";
      $("active").textContent =
        `Tarefa ativa: ${e.task_id.slice(0, 8)} | etapa ${e.index} ${e.role}(${e.agent}) [${e.phase}${e.state ? " " + e.state : ""}]${dur}`;
      if (window.MaestroCanvas) window.MaestroCanvas.onStep(e);
    } else if (e.type === "output") {
      if (window.MaestroCanvas) window.MaestroCanvas.onOutput(e); // terminal ao vivo
    } else if (e.type === "run_end") {
      $("active").textContent = `Tarefa ativa: (nenhuma) — última: ${e.outcome}`;
      if (window.MaestroCanvas) window.MaestroCanvas.onRunEnd(e);
      loadHistory();
      loadAgents();
    }
  };
}

(function init() {
  const tok = localStorage.getItem("maestroToken");
  if (tok) $("token").value = tok;
  refreshAll().catch((e) => ($("history").textContent = "erro: " + e.message));
  connectSSE();
})();
