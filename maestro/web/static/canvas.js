// maestro console — canvas estilo Maestri (V5): terminais ao vivo (read-only) +
// pan/zoom infinito. Cada agente é um "terminal" (foreignObject) mostrando a
// saída AO VIVO via SSE; handoffs são conexões. Sem xterm.js/framework/build.
"use strict";
(function () {
  const SVG = "http://www.w3.org/2000/svg";
  const XHTML = "http://www.w3.org/1999/xhtml";
  const svg = document.getElementById("canvas");
  const COLORS = { idle: "#6b7280", busy: "#3b82f6", blocked: "#f59e0b", failed: "#ef4444", done: "#22c55e" };
  const ST_MAP = { DONE: "done", BLOCKED: "blocked", FAILED: "failed", NEEDS_INPUT: "blocked" };
  const W = 240, H = 150, MAXBUF = 4000;

  let agents = [], route = [], pos = {};
  const state = {}, buf = {};                    // estado e buffer de saída por agente
  let vb = { x: 0, y: 0, w: 900, h: 380 }, saveT = null;

  function tok() { const t = localStorage.getItem("maestroToken"); return t ? { "X-Maestro-Token": t } : {}; }
  async function jget(u) { try { return await (await fetch(u, { headers: tok() })).json(); } catch { return null; } }
  function jpost(u, b) { fetch(u, { method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, tok()), body: JSON.stringify(b) }).catch(() => {}); }
  function applyVB() { svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); }
  function persistVB() { clearTimeout(saveT); saveT = setTimeout(() => jpost("/api/viewport", vb), 400); }
  function scale() { return vb.w / (svg.clientWidth || 900); }
  function stripAnsi(s) { return s.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, ""); }
  function el(tag, a) { const e = document.createElementNS(SVG, tag); for (const k in a) e.setAttribute(k, a[k]); return e; }
  function defaultPos(i, n) { const Wd = 900, M = 140; return { x: n > 1 ? M + (i * (Wd - 2 * M)) / (n - 1) : Wd / 2, y: 190 }; }

  function render() {
    svg.innerHTML = "";
    const defs = el("defs", {});
    const m = el("marker", { id: "arrow", markerWidth: 9, markerHeight: 9, refX: 8, refY: 3, orient: "auto" });
    m.appendChild(el("path", { d: "M0,0 L8,3 L0,6 Z", fill: "#566" })); defs.appendChild(m); svg.appendChild(defs);
    // conexões (handoffs) — de borda a borda dos cards
    for (let i = 0; i < route.length - 1; i++) {
      const a = pos[route[i]], b = pos[route[i + 1]];
      if (a && b) svg.appendChild(el("line", { x1: a.x + W / 2, y1: a.y, x2: b.x - W / 2, y2: b.y, stroke: "#566", "stroke-width": 2, "marker-end": "url(#arrow)" }));
    }
    // terminais (nós)
    agents.forEach((a) => {
      const p = pos[a.id] || { x: 450, y: 190 };
      const vis = state[a.id] || a.state || "idle";
      const fo = el("foreignObject", { x: p.x - W / 2, y: p.y - H / 2, width: W, height: H });
      const box = document.createElementNS(XHTML, "div");
      box.setAttribute("class", "term"); box.setAttribute("data-agent", a.id);
      box.style.borderColor = COLORS[vis] || COLORS.idle;
      const title = document.createElementNS(XHTML, "div");
      title.setAttribute("class", "term-title"); title.style.background = COLORS[vis] || COLORS.idle;
      title.textContent = `${a.id} · ${vis}`;
      title.addEventListener("pointerdown", (e) => startDrag(e, a.id));
      const body = document.createElementNS(XHTML, "pre");
      body.setAttribute("class", "term-body"); body.textContent = buf[a.id] || "";
      box.appendChild(title); box.appendChild(body); fo.appendChild(box); svg.appendChild(fo);
    });
    autoscroll();
  }
  function autoscroll() { svg.querySelectorAll("pre.term-body").forEach((b) => (b.scrollTop = b.scrollHeight)); }

  let drag = null;
  function startDrag(e, id) {
    e.stopPropagation(); const p = pos[id];
    drag = { id, sx: e.clientX, sy: e.clientY, ox: p.x, oy: p.y };
  }
  window.addEventListener("pointermove", (e) => {
    if (!drag) return; const s = scale();
    pos[drag.id] = { x: drag.ox + (e.clientX - drag.sx) * s, y: drag.oy + (e.clientY - drag.sy) * s };
    render();
  });
  window.addEventListener("pointerup", () => { if (drag) { jpost("/api/positions", { agent_id: drag.id, x: pos[drag.id].x, y: pos[drag.id].y }); drag = null; } });

  // pan no fundo + zoom na roda
  let pan = null;
  svg.addEventListener("pointerdown", (e) => { if (e.target === svg || e.target.tagName === "line") { pan = { sx: e.clientX, sy: e.clientY, ox: vb.x, oy: vb.y }; } });
  svg.addEventListener("pointermove", (e) => { if (!pan) return; const s = scale(); vb.x = pan.ox - (e.clientX - pan.sx) * s; vb.y = pan.oy - (e.clientY - pan.sy) * s; applyVB(); });
  svg.addEventListener("pointerup", () => { if (pan) { pan = null; persistVB(); } });
  svg.addEventListener("wheel", (e) => {
    e.preventDefault(); const f = e.deltaY < 0 ? 0.9 : 1.1; const r = svg.getBoundingClientRect();
    const cx = vb.x + ((e.clientX - r.left) / r.width) * vb.w, cy = vb.y + ((e.clientY - r.top) / r.height) * vb.h;
    vb.w = Math.max(160, Math.min(8000, vb.w * f)); vb.h = Math.max(80, Math.min(4000, vb.h * f));
    vb.x = cx - ((e.clientX - r.left) / r.width) * vb.w; vb.y = cy - ((e.clientY - r.top) / r.height) * vb.h;
    applyVB(); persistVB();
  }, { passive: false });

  function appendOut(id, chunk) {
    buf[id] = ((buf[id] || "") + stripAnsi(chunk)).slice(-MAXBUF);
    const b = svg.querySelector(`.term[data-agent="${id}"] pre.term-body`);
    if (b) { b.textContent = buf[id]; b.scrollTop = b.scrollHeight; } else { render(); }
  }

  window.MaestroCanvas = {
    async setAgents(list) {
      agents = list; pos = (await jget("/api/positions")) || {};
      const v = await jget("/api/viewport"); if (v && v.w) vb = v;
      agents.forEach((a, i) => { if (!pos[a.id]) pos[a.id] = defaultPos(i, agents.length); });
      applyVB(); render();
    },
    setRoute(ids) { route = ids || []; render(); },
    onStep(e) { state[e.agent] = e.phase === "start" ? "busy" : (ST_MAP[e.state] || "idle"); render(); },
    onRunEnd() {},
    onOutput(e) { if (e && e.agent) appendOut(e.agent, e.chunk || ""); },   // terminal ao vivo
  };
})();
