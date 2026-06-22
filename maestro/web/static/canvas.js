// maestro console — canvas SVG mínimo (V4-S5). Nós=agentes, conexões=handoffs.
// Sem terminal emulator, sem animações pesadas, sem framework.
"use strict";
(function () {
  const SVG = "http://www.w3.org/2000/svg";
  const svg = document.getElementById("canvas");
  const COLORS = { idle: "#6b7280", busy: "#3b82f6", blocked: "#f59e0b", failed: "#ef4444", done: "#22c55e" };
  const ST_MAP = { DONE: "done", BLOCKED: "blocked", FAILED: "failed", NEEDS_INPUT: "blocked" };

  let agents = [];          // [{id,type,state}]
  let route = [];           // [agentId,...]
  let pos = {};             // id -> {x,y}
  const state = {};         // id -> visual state

  function tok() {
    const t = localStorage.getItem("maestroToken");
    return t ? { "X-Maestro-Token": t } : {};
  }
  async function loadPositions() {
    try { pos = await (await fetch("/api/positions", { headers: tok() })).json(); } catch { pos = {}; }
  }
  function savePosition(id, x, y) {
    fetch("/api/positions", {
      method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, tok()),
      body: JSON.stringify({ agent_id: id, x, y }),
    }).catch(() => {});
  }
  function defaultPos(i, n) {
    const W = 800, M = 90;
    const x = n > 1 ? M + (i * (W - 2 * M)) / (n - 1) : W / 2;
    return { x, y: 160 };
  }
  function el(tag, attrs) {
    const e = document.createElementNS(SVG, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function render() {
    svg.innerHTML = "";
    // conexões (handoffs) seguindo a rota selecionada
    for (let i = 0; i < route.length - 1; i++) {
      const a = pos[route[i]], b = pos[route[i + 1]];
      if (a && b) svg.appendChild(el("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, stroke: "#3a4250", "stroke-width": 2, "marker-end": "url(#arrow)" }));
    }
    // marcador de seta
    const defs = el("defs", {});
    const m = el("marker", { id: "arrow", markerWidth: 8, markerHeight: 8, refX: 7, refY: 3, orient: "auto" });
    m.appendChild(el("path", { d: "M0,0 L7,3 L0,6 Z", fill: "#3a4250" }));
    defs.appendChild(m); svg.appendChild(defs);
    // nós (agentes)
    agents.forEach((a) => {
      const p = pos[a.id] || { x: 400, y: 160 };
      const vis = state[a.id] || a.state || "idle";
      const g = el("g", { transform: `translate(${p.x},${p.y})`, style: "cursor:grab" });
      g.appendChild(el("circle", { r: 26, fill: COLORS[vis] || COLORS.idle, stroke: "#0e1116", "stroke-width": 3 }));
      const label = el("text", { "text-anchor": "middle", y: 44, fill: "#e6e6e6", "font-size": 12 });
      label.textContent = a.id;
      g.appendChild(label);
      makeDraggable(g, a.id);
      svg.appendChild(g);
    });
  }

  function makeDraggable(g, id) {
    let drag = null;
    g.addEventListener("pointerdown", (e) => {
      const p = pos[id]; drag = { sx: e.clientX, sy: e.clientY, ox: p.x, oy: p.y }; g.setPointerCapture(e.pointerId);
    });
    g.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const scale = svg.viewBox.baseVal.width / svg.clientWidth || 1;
      pos[id] = { x: drag.ox + (e.clientX - drag.sx) * scale, y: drag.oy + (e.clientY - drag.sy) * scale };
      render();
    });
    g.addEventListener("pointerup", () => { if (drag) { savePosition(id, pos[id].x, pos[id].y); drag = null; } });
  }

  window.MaestroCanvas = {
    async setAgents(list) {
      agents = list;
      await loadPositions();
      agents.forEach((a, i) => { if (!pos[a.id]) pos[a.id] = defaultPos(i, agents.length); });
      render();
    },
    setRoute(agentIds) { route = agentIds || []; render(); },
    onStep(e) {
      state[e.agent] = e.phase === "start" ? "busy" : (ST_MAP[e.state] || "idle");
      render();
    },
    onRunEnd() { /* estados finais já vieram dos steps */ },
  };
})();
