"use strict";
// tensorcad — projeto com vários casos (W4): lista de casos, rascunho no navegador,
// salvar/abrir .json (formato tensorcad-projeto v1) e exportar .xlsx.
// Opções de layout (T1): "inclinado_45" (casos na raiz do projeto, como antes) e
// "horizontal" (casos e parâmetros próprios em p.horizontal); cada uma com sua lista.
// Usa os globais de app.js ($, estado, aoTrocarCarcaca, agendarCalculo, obter, numero).

const Projeto = (() => {
  const FORMATO = "tensorcad-projeto";
  const VERSAO = 1;
  const LAYOUTS = ["inclinado_45", "horizontal"];
  const CHAVE_RASCUNHO = "tensorcad.projeto.v1";
  let p = null;
  let carregando = false;
  let timerRascunho = null;
  let timerAviso = null;

  const copia = (o) => JSON.parse(JSON.stringify(o));
  const texto = (v) => (v === null || v === undefined ? "" : String(v));
  const primeiraCarcaca = () => (estado.carcacas.find((c) => carcacaCalculavel(c)) || {}).carcaca || "";

  function casoVazio(nome) {
    return { caso_id: nome, carcaca: primeiraCarcaca(), motor_id: null, R_min: "", R_max: "",
      R2_min: "", R2_max: "", ajustes: { chapa: {}, motor: {} }, _status: "" };
  }
  function horizontalVazio() {
    return { altura_tubo: "", comprimento_tubo: "", invertido: false, ativo: 0, casos: [casoVazio("th-1")] };
  }
  function novoProjeto() {
    return { formato: FORMATO, versao: VERSAO, nome: "PROJETO", layout: "inclinado_45", cota: "",
      banco_duplo: false, ativo: 0, casos: [casoVazio("caso-1")], horizontal: horizontalVazio() };
  }
  // lista de casos da opção de layout em uso (o projeto, no 45°; p.horizontal, no tubo horizontal)
  const L = () => (p.layout === "horizontal" ? p.horizontal : p);
  const ativo = () => L().casos[L().ativo];

  function nomeLivre(base) {
    const usados = new Set(L().casos.map((c) => c.caso_id.toLowerCase()));
    if (!usados.has(base.toLowerCase())) return base;
    for (let i = 2; ; i++) if (!usados.has(`${base}-${i}`.toLowerCase())) return `${base}-${i}`;
  }

  // ---------------------------------------------------------------- avisos e downloads
  function aviso(msg, tipo = "info", ms = 4500) {
    const el = $("aviso");
    el.textContent = msg;
    el.dataset.tipo = tipo;
    el.hidden = false;
    clearTimeout(timerAviso);
    timerAviso = setTimeout(() => (el.hidden = true), ms);
  }
  function baixar(blob, nome) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nome;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  const nomeArquivo = () => (p.nome || "projeto").replace(/[^\w\-. ]/g, "_").trim() || "projeto";

  // ---------------------------------------------------------------- formulário ↔ caso ativo
  function lerFormulario() {
    if (!p || carregando) return;
    p.nome = $("nome-projeto").value;
    p.cota = $("cota").value.trim();
    p.banco_duplo = $("banco-duplo").checked;
    p.horizontal.altura_tubo = $("altura-tubo").value.trim();
    p.horizontal.comprimento_tubo = $("comprimento-tubo").value.trim();
    p.horizontal.invertido = $("motor-invertido").checked;
    const c = ativo();
    c.caso_id = $("caso_id").value.trim();
    c.carcaca = $("carcaca").value;
    c.motor_id = $("motor_id").value || null;
    c.R_min = $("R_min").value.trim();
    c.R_max = $("R_max").value.trim();
    c.R2_min = $("R2_min").value.trim();
    c.R2_max = $("R2_max").value.trim();
    c.ajustes = copia(estado.ajustes);
    renderLista();
    agendarRascunho();
  }

  function carregarNoFormulario() {
    carregando = true;
    $("nome-projeto").value = p.nome;
    $("cota").value = texto(p.cota);
    $("banco-duplo").checked = Boolean(p.banco_duplo);
    mostrarBancoDuplo();
    aplicarLayout();
    $("altura-tubo").value = texto(p.horizontal.altura_tubo);
    $("comprimento-tubo").value = texto(p.horizontal.comprimento_tubo);
    $("motor-invertido").checked = Boolean(p.horizontal.invertido);
    const c = ativo();
    $("caso_id").value = c.caso_id;
    $("R_min").value = texto(c.R_min);
    $("R_max").value = texto(c.R_max);
    $("R2_min").value = texto(c.R2_min);
    $("R2_max").value = texto(c.R2_max);
    const info = estado.carcacas.find((x) => x.carcaca === c.carcaca && carcacaCalculavel(x));
    $("carcaca").value = info ? c.carcaca : primeiraCarcaca();
    estado.ajustes = info ? copia(c.ajustes || { chapa: {}, motor: {} }) : { chapa: {}, motor: {} };
    aoTrocarCarcaca(null, { manterAjustes: true, motorId: c.motor_id });
    carregando = false;
    lerFormulario();
    agendarCalculo();
    renderLista();
  }

  function errosLocais() {
    if (!p) return {};
    const nome = ativo().caso_id;
    if (!nome) return { caso_id: "o caso precisa de um nome" };
    const repetido = L().casos.some((c, i) => i !== L().ativo && c.caso_id.toLowerCase() === nome.toLowerCase());
    return repetido ? { caso_id: "já existe um caso com este nome" } : {};
  }

  function definirStatus(st) {
    if (!p) return;
    ativo()._status = st;
    renderLista();
  }

  function renderLista() {
    const ul = $("lista-casos");
    ul.replaceChildren();
    L().casos.forEach((c, i) => {
      const li = document.createElement("li");
      li.dataset.indice = i;
      li.classList.toggle("ativo", i === L().ativo);
      const ponto = document.createElement("span");
      ponto.className = "ponto";
      ponto.dataset.status = c._status === "ERRO" ? "SEM_SOLUCAO" : c._status;
      ponto.title = c._status || "não calculado";
      const nome = document.createElement("span");
      nome.className = "nome-caso";
      nome.textContent = c.caso_id || "(sem nome)";
      const info = document.createElement("span");
      info.className = "info-caso";
      info.textContent = `${c.carcaca || "—"} · ${c.R_min || "?"}/${c.R_max || "?"}`;
      li.append(ponto, nome, info);
      li.addEventListener("click", () => ativar(i));
      ul.append(li);
    });
    $("contagem-casos").textContent = `(${L().casos.length})`;
    $("btn-caso-excluir").disabled = L().casos.length < 2;
  }

  function ativar(i) {
    if (i === L().ativo) return;
    lerFormulario();
    L().ativo = i;
    carregarNoFormulario();
  }

  // ---------------------------------------------------------------- casos
  function novoCaso() {
    lerFormulario();
    const prefixo = p.layout === "horizontal" ? "th" : "caso";
    const c = casoVazio(nomeLivre(`${prefixo}-${L().casos.length + 1}`));
    c.carcaca = ativo().carcaca || c.carcaca;
    L().casos.push(c);
    L().ativo = L().casos.length - 1;
    carregarNoFormulario();
    $("caso_id").focus();
  }
  function duplicar() {
    lerFormulario();
    const c = copia(ativo());
    c.caso_id = nomeLivre(`${c.caso_id || "caso"}-copia`);
    L().casos.splice(L().ativo + 1, 0, c);
    L().ativo += 1;
    carregarNoFormulario();
  }
  function excluir() {
    if (L().casos.length < 2) return;
    if (!window.confirm(`Excluir o caso "${ativo().caso_id}"?`)) return;
    L().casos.splice(L().ativo, 1);
    L().ativo = Math.min(L().ativo, L().casos.length - 1);
    carregarNoFormulario();
  }

  // ---------------------------------------------------------------- serialização
  const num = (t) => {
    const s = texto(t).trim();
    if (s === "") return null;
    const x = numero(s);
    return Number.isFinite(x) ? x : s;
  };
  function serializarCasos(casos) {
    const grupo = (g) => Object.fromEntries(Object.entries(g || {}).map(([k, v]) => [k, num(v)]));
    return casos.map((c) => ({
      caso_id: c.caso_id,
      carcaca: c.carcaca,
      motor_id: c.motor_id,
      R_min: num(c.R_min),
      R_max: num(c.R_max),
      R2_min: num(c.R2_min),
      R2_max: num(c.R2_max),
      ajustes: { chapa: grupo(c.ajustes?.chapa), motor: grupo(c.ajustes?.motor) },
      g_manual: Array.isArray(c.g_manual) && c.g_manual.some((v) => v !== null) ? c.g_manual : null,
    }));
  }
  function serializar() {
    const h = p.horizontal;
    return {
      formato: FORMATO,
      versao: VERSAO,
      nome: p.nome,
      layout: p.layout,
      cota: num(p.cota),
      banco_duplo: Boolean(p.banco_duplo),
      casos: serializarCasos(p.casos),
      horizontal: {
        altura_tubo: num(h.altura_tubo),
        comprimento_tubo: num(h.comprimento_tubo),
        invertido: Boolean(h.invertido),
        casos: serializarCasos(h.casos),
      },
    };
  }
  function normalizarCasos(casos, prefixo) {
    const grupo = (g) => Object.fromEntries(Object.entries(g || {}).map(([k, v]) => [k, texto(v)]));
    return casos.map((c, i) => ({
      caso_id: texto(c.caso_id) || `${prefixo}-${i + 1}`,
      carcaca: texto(c.carcaca),
      motor_id: c.motor_id || null,
      R_min: texto(c.R_min),
      R_max: texto(c.R_max),
      R2_min: texto(c.R2_min),
      R2_max: texto(c.R2_max),
      ajustes: { chapa: grupo(c.ajustes?.chapa), motor: grupo(c.ajustes?.motor) },
      g_manual: Array.isArray(c.g_manual)
        ? [0, 1].map((k) => (c.g_manual[k] === null || c.g_manual[k] === undefined ? null : Number(c.g_manual[k])))
        : null,
      _status: "",
    }));
  }
  const indice = (v, n) => Math.min(Math.max(0, Number(v) || 0), n - 1);
  function normalizar(obj) {
    if (!obj || obj.formato !== FORMATO) throw new Error("arquivo não é um projeto do tensorcad");
    if (obj.versao !== VERSAO) throw new Error(`versão de projeto não suportada: ${obj.versao}`);
    if (!Array.isArray(obj.casos) || obj.casos.length === 0) throw new Error("projeto sem casos");
    const layout = obj.layout ?? "inclinado_45"; // arquivos anteriores à T1: 45°
    if (!LAYOUTS.includes(layout)) throw new Error(`opção de layout desconhecida: ${layout}`);
    const h = obj.horizontal || {};
    const casosH = Array.isArray(h.casos) && h.casos.length ? normalizarCasos(h.casos, "th") : horizontalVazio().casos;
    return {
      formato: FORMATO,
      versao: VERSAO,
      nome: texto(obj.nome) || "PROJETO",
      layout,
      cota: texto(obj.cota),
      banco_duplo: Boolean(obj.banco_duplo),
      ativo: indice(obj.ativo, obj.casos.length),
      casos: normalizarCasos(obj.casos, "caso"),
      horizontal: {
        altura_tubo: texto(h.altura_tubo),
        comprimento_tubo: texto(h.comprimento_tubo),
        invertido: Boolean(h.invertido),
        ativo: indice(h.ativo, casosH.length),
        casos: casosH,
      },
    };
  }

  // ---------------------------------------------------------------- rascunho
  function agendarRascunho() {
    clearTimeout(timerRascunho);
    timerRascunho = setTimeout(() => {
      try {
        const dados = serializar();
        dados.ativo = p.ativo;
        dados.horizontal.ativo = p.horizontal.ativo;
        localStorage.setItem(CHAVE_RASCUNHO, JSON.stringify(dados));
      } catch (_e) {
        /* armazenamento indisponível: segue sem rascunho */
      }
    }, 400);
  }
  function lerRascunho() {
    try {
      const bruto = localStorage.getItem(CHAVE_RASCUNHO);
      return bruto ? normalizar(JSON.parse(bruto)) : null;
    } catch (_e) {
      return null;
    }
  }

  // ---------------------------------------------------------------- arquivos
  function salvarJson() {
    lerFormulario();
    const blob = new Blob([JSON.stringify(serializar(), null, 2)], { type: "application/json" });
    baixar(blob, `${nomeArquivo()}.json`);
    aviso(`projeto salvo: ${nomeArquivo()}.json (${p.casos.length} caso(s) 45°, ${p.horizontal.casos.length} tubo horizontal)`);
  }

  async function abrirArquivo(arquivo) {
    try {
      const obj = normalizar(JSON.parse(await arquivo.text()));
      p = obj;
      carregarNoFormulario();
      atualizarStatusTodos();
      aviso(`projeto aberto: ${p.nome} (${L().casos.length} caso(s))`);
    } catch (e) {
      aviso(`Não foi possível abrir: ${e.message}`, "erro", 7000);
    }
  }

  async function exportar() {
    lerFormulario();
    try {
      const r = await fetch("/api/exportar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(serializar()),
      });
      if (!r.ok) {
        const d = await r.json();
        const linhas = Object.entries(d.erros || {}).map(([k, v]) => {
          const m = /^(horizontal\.)?casos\[(\d+)\]\.(.*)$/.exec(k);
          if (!m) return `${k}: ${v}`;
          const lista = m[1] ? p.horizontal.casos : p.casos;
          const onde = m[1] ? "tubo horizontal" : "45°";
          return `${lista[Number(m[2])].caso_id} (${onde}): ${m[3]} — ${v}`;
        });
        aviso(`Exportação recusada:\n${linhas.join("\n") || d.erro}`, "erro", 9000);
        return;
      }
      baixar(await r.blob(), `${nomeArquivo()}.xlsx`);
      aviso(`planilha exportada: ${nomeArquivo()}.xlsx (uma aba por caso preenchido, nos dois layouts)`);
    } catch (e) {
      aviso(`Erro ao exportar: ${e.message}`, "erro", 7000);
    }
  }

  async function atualizarStatusTodos() {
    const h = p.layout === "horizontal";
    const banco = (c) => ({ ativo: p.banco_duplo && Boolean(c.R2_min || c.R2_max), R2_min: c.R2_min, R2_max: c.R2_max });
    for (const [i, c] of L().casos.entries()) {
      if (i === L().ativo) continue;
      if (!c.R_min || !c.R_max) continue;
      if (h && !p.horizontal.comprimento_tubo) continue;
      const corpo = h
        ? { ...c, banco_duplo: banco(c), altura_tubo: p.horizontal.altura_tubo || null,
            g_manual: p.horizontal.altura_tubo ? c.g_manual || null : null,
            comprimento_tubo: p.horizontal.comprimento_tubo, invertido: p.horizontal.invertido }
        : { ...c, banco_duplo: banco(c), cota: p.cota || null };
      try {
        const r = await obter(h ? "/api/calcular_horizontal" : "/api/calcular", {
          method: "POST",
          body: JSON.stringify(corpo),
        });
        c._status = r.status;
      } catch (_e) {
        c._status = "ERRO";
      }
    }
    renderLista();
  }

  // ---------------------------------------------------------------- opção de layout
  const NOMES_LAYOUT = { inclinado_45: "tubo inclinado 45°", horizontal: "tubo horizontal" };
  function aplicarLayout() {
    document.body.dataset.layout = p.layout;
    for (const r of document.querySelectorAll("input[name='layout']")) r.checked = r.value === p.layout;
    $("nome-layout").textContent = NOMES_LAYOUT[p.layout];
    atualizarOpcoesCarcaca();
  }
  function trocarLayout(layout) {
    if (!LAYOUTS.includes(layout) || layout === p.layout) return;
    lerFormulario();
    p.layout = layout;
    carregarNoFormulario();
    atualizarStatusTodos();
    aviso(`opção de layout: ${NOMES_LAYOUT[layout]} (${L().casos.length} caso(s))`);
  }

  function limpar() {
    lerFormulario();
    const n = p.casos.length + p.horizontal.casos.length;
    const msg =
      `Limpar a memória?\n\nOs ${p.casos.length} caso(s) do tubo inclinado 45° e ` +
      `${p.horizontal.casos.length} do tubo horizontal do projeto "${p.nome}" serão apagados deste navegador.\n` +
      "Para guardá-los, cancele e use \"salvar .json\" ou \"exportar .xlsx\" antes.";
    if (!window.confirm(msg)) return;
    p = novoProjeto();
    try {
      localStorage.removeItem(CHAVE_RASCUNHO);
    } catch (_e) {
      /* ignora */
    }
    carregarNoFormulario();
    aviso(`memória limpa: ${n} caso(s) apagado(s)`);
  }

  function iniciar() {
    const rascunho = lerRascunho();
    p = rascunho || novoProjeto();
    $("btn-limpar").addEventListener("click", limpar);
    $("btn-salvar").addEventListener("click", salvarJson);
    $("btn-exportar").addEventListener("click", exportar);
    $("btn-abrir").addEventListener("click", () => $("arquivo-projeto").click());
    $("arquivo-projeto").addEventListener("change", (ev) => {
      const f = ev.target.files[0];
      ev.target.value = "";
      if (f) abrirArquivo(f);
    });
    $("btn-caso-novo").addEventListener("click", novoCaso);
    $("btn-caso-novo-lista").addEventListener("click", novoCaso);
    $("btn-caso-duplicar").addEventListener("click", duplicar);
    $("btn-caso-excluir").addEventListener("click", excluir);
    for (const r of document.querySelectorAll("input[name='layout']")) {
      r.addEventListener("change", () => r.checked && trocarLayout(r.value));
    }
    for (const id of ["altura-tubo", "comprimento-tubo", "motor-invertido"]) {
      $(id).addEventListener(id === "motor-invertido" ? "change" : "input", agendarCalculo);
    }
    carregarNoFormulario();
    if (rascunho) {
      aviso(`rascunho restaurado: ${p.nome} (${L().casos.length} caso(s))`);
      atualizarStatusTodos();
    }
  }

  // ajuste manual de g do caso ativo (tubo horizontal): [g 0 %, g 3 %], null = calculado
  const gManual = () => {
    const g = ativo().g_manual;
    return Array.isArray(g) ? [...g] : [null, null];
  };
  function definirGManual(g) {
    ativo().g_manual = g.some((v) => v !== null) ? g : null;
    agendarRascunho();
  }

  return {
    iniciar,
    aviso,
    gManual,
    definirGManual,
    lerFormulario,
    errosLocais,
    definirStatus,
    serializar,
    trocarLayout,
    layout: () => (p ? p.layout : "inclinado_45"),
    estado: () => p,
  };
})();
