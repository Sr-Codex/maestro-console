// maestro console — canvas infinito (V5-S3): pan/zoom + nós/handoffs.
// SVG viewBox p/ pan (arrastar fundo) e zoom (roda); viewport persistido.
"use strict";
(function () {
  const SVG = "http://www.w3.org/2000/svg";
  const svg = document.getElementById("canvas");
  const COLORS = { idle: "#6b7280", busy: "#3b82f6", blocked: "#f59e0b", failed: "#ef4444", done: "#22c55e" };
  const ST_MAP = { DONE: "done", BLOCKED: "blocked", FAILED: "failed", NEEDS_INPUT: "blocked" };

  let agents = [], route = [], pos = {};
  const state = {};
  let vb = { x: 0, y: 0, w: 800, h: 320 };       // viewport (infinito via pan/zoom)
  let saveT = null;

  function tok() {
    const t = localStorage.getItem("maestroToken");
    return t ? { "X-Maestro-Token": t } : {};
  }
  async function jget(u) { try { return await (await fetch(u, { headers: tok() })).json(); } catch { return null; } }
  function jpost(u, body) {
    fetch(u, { method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, tok()), body: JSON.stringify(body) }).catch(() => {});
  }
  function applyVB() { svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); }
  function persistVB() { clearTimeout(saveT); saveT = setTimeout(() => jpost("/api/viewport", vb), 400); }
  function scale() { return vb.w / (svg.clientWidth || 800); }
  function el(tag, a) { const e = document.createElementNS(SVG, tag); for (const k in a) e.setAttribute(k, a[k]); return e; }
  function defaultPos(i, n) { const W = 800, M = 90; return { x: n > 1 ? M + (i * (W - 2 * M)) / (n - 1) : W / 2, y: 160 }; }

  function render() {
    svg.innerHTML = "";
    const defs = el("defs", {});
    const m = el("marker", { id: "arrow", markerWidth: 8, markerHeight: 8, refX: 7, refY: 3, orient: "auto" });
    m.appendChild(el("path", { d: "M0,0 L7,3 L0,6 Z", fill: "#3a4250" })); defs.appendChild(m); svg.appendChild(defs);
    for (let i = 0; i < route.length - 1; i++) {
      const a = pos[route[i]], b = pos[route[i + 1]];
      if (a && b) svg.appendChild(el("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, stroke: "#3a4250", "stroke-width": 2, "marker-end": "url(#arrow)" }));
    }
    agents.forEach((a) => {
      const p = pos[a.id] || { x: 400, y: 160 };
      const vis = state[a.id] || a.state || "idle";
      const g = el("g", { transform: `translate(${p.x},${p.y})`, style: "cursor:grab" });
      g.appendChild(el("circle", { r: 26, fill: COLORS[vis] || COLORS.idle, stroke: "#0e1116", "stroke-width": 3 }));
      const t = el("text", { "text-anchor": "middle", y: 44, fill: "#e6e6e6", "font-size": 12 }); t.textContent = a.id; g.appendChild(t);
      nodeDrag(g, a.id); svg.appendChild(g);
    });
  }

  function nodeDrag(g, id) {
    let d = null;
    g.addEventListener("pointerdown", (e) => { e.stopPropagation(); const p = pos[id]; d = { sx: e.clientX, sy: e.clientY, ox: p.x, oy: p.y }; g.setPointerCapture(e.pointerId); });
    g.addEventListener("pointermove", (e) => { if (!d) return; const s = scale(); pos[id] = { x: d.ox + (e.clientX - d.sx) * s, y: d.oy + (e.clientY - d.sy) * s }; render(); });
    g.addEventListener("pointerup", () => { if (d) { jpost("/api/positions", { agent_id: id, x: pos[id].x, y: pos[id].y }); d = null; } });
  }

  // pan no fundo
  let pan = null;
  svg.addEventListener("pointerdown", (e) => { if (e.target === svg || e.target.tagName === "line") { pan = { sx: e.clientX, sy: e.clientY, ox: vb.x, oy: vb.y }; svg.setPointerCapture(e.pointerId); } });
  svg.addEventListener("pointermove", (e) => { if (!pan) return; const s = scale(); vb.x = pan.ox - (e.clientX - pan.sx) * s; vb.y = pan.oy - (e.clientY - pan.sy) * s; applyVB(); });
  svg.addEventListener("pointerup", () => { if (pan) { pan = null; persistVB(); } });
  // zoom na roda (em torno do cursor)
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const f = e.deltaY < 0 ? 0.9 : 1.1;
    const r = svg.getBoundingClientRect();
    const cx = vb.x + ((e.clientX - r.left) / r.width) * vb.w;
    const cy = vb.y + ((e.clientY - r.top) / r.height) * vb.h;
    vb.w = Math.max(120, Math.min(6000, vb.w * f)); vb.h = Math.max(60, Math.min(3000, vb.h * f));
    vb.x = cx - ((e.clientX - r.left) / r.width) * vb.w;
    vb.y = cy - ((e.clientY - r.top) / r.height) * vb.h;
    applyVB(); persistVB();
  }, { passive: false });

  window.MaestroCanvas = {
    async setAgents(list) {
      agents = list;
      pos = (await jget("/api/positions")) || {};
      const v = await jget("/api/viewport"); if (v && v.w) vb = v;
      agents.forEach((a, i) => { if (!pos[a.id]) pos[a.id] = defaultPos(i, agents.length); });
      applyVB(); render();
    },
    setRoute(ids) { route = ids || []; render(); },
    onStep(e) { state[e.agent] = e.phase === "start" ? "busy" : (ST_MAP[e.state] || "idle"); render(); },
    onRunEnd() {},
    onOutput() {},   // V5-S4 preenche os terminais ao vivo
  };
})();
