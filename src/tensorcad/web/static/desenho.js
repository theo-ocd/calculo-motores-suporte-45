"use strict";
// tensorcad — desenho interativo (W2). Coordenadas recebidas: X→ direita, Y↑ cima, mm, origem O.
// No SVG: x = X, y = −Y. Traços com vector-effect: espessura constante na tela.

const Desenho = (() => {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const PX_TEXTO = 12;
  const PX_PONTO = 3.5;
  const PX_SETA = 7;
  let svg, mundo, dica, xy;
  let vb = null; // {x, y, w, h} em unidades do SVG (mm)
  let dados = null;
  let arrasto = null;
  const camadasOcultas = new Set();

  const fmt = (v, c = 2) =>
    typeof v === "number"
      ? v.toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c })
      : v === null || v === undefined ? "—" : String(v);

  function el(nome, attrs = {}, pai = null) {
    const e = document.createElementNS(SVG_NS, nome);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (pai) pai.append(e);
    return e;
  }
  const P = ([X, Y]) => [X, -Y];

  // -------------------------------------------------------------- visão (viewBox)
  function mmPorPx() {
    return vb ? vb.w / Math.max(svg.clientWidth, 1) : 1;
  }
  function aplicarVisao() {
    if (!vb) return;
    // mantém a proporção do elemento (sem distorção)
    const asp = svg.clientHeight / Math.max(svg.clientWidth, 1);
    vb.h = vb.w * asp;
    svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
    const u = mmPorPx();
    for (const t of mundo.querySelectorAll("text")) t.setAttribute("font-size", PX_TEXTO * u);
    for (const p of mundo.querySelectorAll("circle.ponto")) p.setAttribute("r", PX_PONTO * u);
    for (const t of mundo.querySelectorAll("text[data-dx]")) {
      t.setAttribute("x", Number(t.dataset.x0) + Number(t.dataset.dx) * u);
      t.setAttribute("y", Number(t.dataset.y0) + Number(t.dataset.dy) * u);
    }
    for (const s of mundo.querySelectorAll("path.seta")) desenharSeta(s, u);
    svg.dispatchEvent(new CustomEvent("visao", { detail: { ...vb } }));
  }
  function ajustar() {
    if (!dados) return;
    const [x0, y0, x1, y1] = dados.limites; // em X/Y de desenho
    const m = 0.08 * Math.max(x1 - x0, y1 - y0);
    const w = x1 - x0 + 2 * m;
    const h = y1 - y0 + 2 * m;
    const asp = svg.clientHeight / Math.max(svg.clientWidth, 1);
    const largura = Math.max(w, h / asp);
    const cx = (x0 + x1) / 2;
    const cy = -(y0 + y1) / 2;
    vb = { x: cx - largura / 2, y: cy - (largura * asp) / 2, w: largura, h: largura * asp };
    aplicarVisao();
  }
  function zoom(fator, px = null, py = null) {
    if (!vb) return;
    const r = svg.getBoundingClientRect();
    const fx = px === null ? 0.5 : (px - r.left) / r.width;
    const fy = py === null ? 0.5 : (py - r.top) / r.height;
    const ax = vb.x + fx * vb.w;
    const ay = vb.y + fy * vb.h;
    vb.w *= fator;
    vb.h *= fator;
    vb.x = ax - fx * vb.w;
    vb.y = ay - fy * vb.h;
    aplicarVisao();
  }
  function paraDesenho(ev) {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const q = pt.matrixTransform(svg.getScreenCTM().inverse());
    return [q.x, -q.y];
  }

  // -------------------------------------------------------------- primitivas
  function desenharSeta(path, u) {
    const [x, y, ang] = path.dataset.ponta.split(",").map(Number);
    const s = PX_SETA * u;
    const a1 = ang + Math.PI - 0.35;
    const a2 = ang + Math.PI + 0.35;
    path.setAttribute(
      "d",
      `M ${x} ${y} L ${x + s * Math.cos(a1)} ${y + s * Math.sin(a1)} L ${x + s * Math.cos(a2)} ${y + s * Math.sin(a2)} Z`,
    );
  }

  function texto(g, txt, [x, y], dxPx, dyPx, classe = "rotulo", ancora = "middle") {
    const t = el("text", { class: classe, "text-anchor": ancora, "dominant-baseline": "middle" }, g);
    t.dataset.x0 = x;
    t.dataset.y0 = y;
    t.dataset.dx = dxPx;
    t.dataset.dy = dyPx;
    t.textContent = txt;
    return t;
  }

  function primitiva(g, p) {
    const comum = { class: "el", id: `el-${p.id}`, "data-id": p.id };
    if (p.status) comum["data-status"] = p.status;
    let e;
    switch (p.tipo) {
      case "ponto": {
        const [x, y] = P(p.p);
        e = el("circle", { ...comum, class: "ponto", cx: x, cy: y, r: 1 }, g);
        if (p.id === "O" || p.id === "L") texto(g, p.id, [x, y], 10, -10, "rotulo rotulo-ponto", "start");
        break;
      }
      case "linha": {
        const [x1, y1] = P(p.p0);
        const [x2, y2] = P(p.p1);
        e = el("line", { ...comum, x1, y1, x2, y2 }, g);
        break;
      }
      case "polilinha":
      case "poligono": {
        const pts = p.pts.map(P).map((q) => q.join(",")).join(" ");
        e = el(p.tipo === "poligono" ? "polygon" : "polyline", { ...comum, points: pts }, g);
        if ((p.id === "O" || p.id === "O2") && p.c) texto(g, p.id, P(p.c), 16, -16, "rotulo rotulo-ponto", "start");
        break;
      }
      case "circulo": {
        const [cx, cy] = P(p.c);
        e = el("circle", { ...comum, cx, cy, r: p.r }, g);
        break;
      }
      case "arco": {
        const rad = (a) => (a * Math.PI) / 180;
        const [ox, oy] = p.c || [0, 0];
        const [x0, y0] = P([ox + p.r * Math.cos(rad(p.a0)), oy + p.r * Math.sin(rad(p.a0))]);
        const [x1, y1] = P([ox + p.r * Math.cos(rad(p.a1)), oy + p.r * Math.sin(rad(p.a1))]);
        const grande = Math.abs(p.a1 - p.a0) > 180 ? 1 : 0;
        e = el("path", { ...comum, d: `M ${x0} ${y0} A ${p.r} ${p.r} 0 ${grande} 0 ${x1} ${y1}` }, g);
        // banco 2: rótulo na outra ponta para não sobrepor o do banco 1
        texto(g, p.rotulo, p.camada === "banco2" ? [x0, y0] : [x1, y1], 0, -12);
        break;
      }
      case "cota": {
        const [x1, y1] = P(p.p0);
        const [x2, y2] = P(p.p1);
        e = el("line", { ...comum, x1, y1, x2, y2 }, g);
        const ang = Math.atan2(y2 - y1, x2 - x1);
        for (const [x, y, a] of [[x2, y2, ang], [x1, y1, ang + Math.PI]]) {
          const s = el("path", { class: "seta", fill: "currentColor" }, g);
          s.dataset.ponta = `${x},${y},${a}`;
          s.style.fill = "var(--acento)";
        }
        // texto ao lado do meio da cota, deslocado na normal (px de tela)
        const nx = -Math.sin(ang);
        const ny = Math.cos(ang);
        texto(g, p.rotulo, [(x1 + x2) / 2, (y1 + y2) / 2], 14 * nx, 14 * ny);
        break;
      }
      default:
        return;
    }
    e.dataset.rotulo = p.rotulo;
    e.dataset.info = JSON.stringify(p.info || {});
  }

  function desenhar(d, { reajustar = false } = {}) {
    dados = d;
    mundo.replaceChildren();
    document.getElementById("aviso-desenho").hidden = Boolean(d);
    if (!d) return;
    const grupos = {};
    for (const c of d.camadas) {
      grupos[c] = el("g", { class: c, "data-camada": c }, mundo);
      grupos[c].classList.toggle("oculta", camadasOcultas.has(c));
    }
    for (const p of d.primitivas) primitiva(grupos[p.camada], p);
    if (reajustar || !vb) ajustar();
    else aplicarVisao();
  }

  // -------------------------------------------------------------- interação
  function mostrarDica(ev) {
    const alvo = ev.target.closest("[data-id]");
    if (!alvo || arrasto) {
      dica.hidden = true;
      return;
    }
    const info = JSON.parse(alvo.dataset.info || "{}");
    const linhas = [alvo.dataset.rotulo];
    for (const [k, v] of Object.entries(info)) linhas.push(`${k}: ${fmt(v)}`);
    dica.textContent = linhas.join("\n");
    const r = svg.getBoundingClientRect();
    dica.style.left = `${ev.clientX - r.left + 14}px`;
    dica.style.top = `${ev.clientY - r.top + 14}px`;
    dica.hidden = false;
  }

  function iniciar() {
    svg = document.getElementById("desenho");
    mundo = document.getElementById("mundo");
    dica = document.getElementById("dica-desenho");
    xy = document.getElementById("cursor-xy");

    svg.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      zoom(ev.deltaY > 0 ? 1.15 : 1 / 1.15, ev.clientX, ev.clientY);
    }, { passive: false });
    svg.addEventListener("pointerdown", (ev) => {
      if (!vb || ev.button !== 0) return;
      arrasto = { x: ev.clientX, y: ev.clientY, vx: vb.x, vy: vb.y };
      svg.setPointerCapture(ev.pointerId);
      svg.classList.add("arrastando");
    });
    svg.addEventListener("pointermove", (ev) => {
      const [X, Y] = paraDesenho(ev);
      xy.textContent = `X ${fmt(X, 1)}   Y ${fmt(Y, 1)} mm  (a partir de O; X→, Y↑)`;
      if (arrasto) {
        const u = mmPorPx();
        vb.x = arrasto.vx - (ev.clientX - arrasto.x) * u;
        vb.y = arrasto.vy - (ev.clientY - arrasto.y) * u;
        aplicarVisao();
      }
      mostrarDica(ev);
    });
    const soltar = () => {
      arrasto = null;
      svg.classList.remove("arrastando");
    };
    svg.addEventListener("pointerup", soltar);
    svg.addEventListener("pointercancel", soltar);
    svg.addEventListener("pointerleave", () => (dica.hidden = true));
    svg.addEventListener("dblclick", ajustar);
    document.getElementById("btn-ajustar").addEventListener("click", ajustar);
    document.getElementById("btn-mais").addEventListener("click", () => zoom(1 / 1.3));
    document.getElementById("btn-menos").addEventListener("click", () => zoom(1.3));
    for (const cb of document.querySelectorAll(".ferramentas input[data-camada]")) {
      cb.addEventListener("change", () => {
        const c = cb.dataset.camada;
        if (cb.checked) camadasOcultas.delete(c);
        else camadasOcultas.add(c);
        mundo.querySelector(`[data-camada="${c}"]`)?.classList.toggle("oculta", !cb.checked);
      });
    }
    new ResizeObserver(() => aplicarVisao()).observe(svg);
  }

  return { iniciar, desenhar, ajustar, zoom, visao: () => (vb ? { ...vb } : null) };
})();
