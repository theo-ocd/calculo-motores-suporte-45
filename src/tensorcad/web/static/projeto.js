"use strict";
// tensorcad — projeto com vários casos (W4): lista de casos, rascunho no navegador,
// salvar/abrir .json (formato tensorcad-projeto v1) e exportar .xlsx.
// Usa os globais de app.js ($, estado, aoTrocarCarcaca, agendarCalculo, obter, numero).

const Projeto = (() => {
  const FORMATO = "tensorcad-projeto";
  const VERSAO = 1;
  const CHAVE_RASCUNHO = "tensorcad.projeto.v1";
  let p = null;
  let carregando = false;
  let timerRascunho = null;
  let timerAviso = null;

  const copia = (o) => JSON.parse(JSON.stringify(o));
  const texto = (v) => (v === null || v === undefined ? "" : String(v));
  const primeiraCarcaca = () => (estado.carcacas.find((c) => c.calculavel) || {}).carcaca || "";

  function casoVazio(nome) {
    return { caso_id: nome, carcaca: primeiraCarcaca(), motor_id: null, R_min: "", R_max: "",
      R2_min: "", R2_max: "", ajustes: { chapa: {}, motor: {} }, _status: "" };
  }
  function novoProjeto() {
    return { formato: FORMATO, versao: VERSAO, nome: "PROJETO", cota: "", banco_duplo: false, ativo: 0,
      casos: [casoVazio("caso-1")] };
  }
  const ativo = () => p.casos[p.ativo];

  function nomeLivre(base) {
    const usados = new Set(p.casos.map((c) => c.caso_id.toLowerCase()));
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
    const c = ativo();
    $("caso_id").value = c.caso_id;
    $("R_min").value = texto(c.R_min);
    $("R_max").value = texto(c.R_max);
    $("R2_min").value = texto(c.R2_min);
    $("R2_max").value = texto(c.R2_max);
    const info = estado.carcacas.find((x) => x.carcaca === c.carcaca && x.calculavel);
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
    const repetido = p.casos.some((c, i) => i !== p.ativo && c.caso_id.toLowerCase() === nome.toLowerCase());
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
    p.casos.forEach((c, i) => {
      const li = document.createElement("li");
      li.dataset.indice = i;
      li.classList.toggle("ativo", i === p.ativo);
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
    $("contagem-casos").textContent = `(${p.casos.length})`;
    $("btn-caso-excluir").disabled = p.casos.length < 2;
  }

  function ativar(i) {
    if (i === p.ativo) return;
    lerFormulario();
    p.ativo = i;
    carregarNoFormulario();
  }

  // ---------------------------------------------------------------- casos
  function novoCaso() {
    lerFormulario();
    const c = casoVazio(nomeLivre(`caso-${p.casos.length + 1}`));
    c.carcaca = ativo().carcaca || c.carcaca;
    p.casos.push(c);
    p.ativo = p.casos.length - 1;
    carregarNoFormulario();
    $("caso_id").focus();
  }
  function duplicar() {
    lerFormulario();
    const c = copia(ativo());
    c.caso_id = nomeLivre(`${c.caso_id || "caso"}-copia`);
    p.casos.splice(p.ativo + 1, 0, c);
    p.ativo += 1;
    carregarNoFormulario();
  }
  function excluir() {
    if (p.casos.length < 2) return;
    if (!window.confirm(`Excluir o caso "${ativo().caso_id}"?`)) return;
    p.casos.splice(p.ativo, 1);
    p.ativo = Math.min(p.ativo, p.casos.length - 1);
    carregarNoFormulario();
  }

  // ---------------------------------------------------------------- serialização
  const num = (t) => {
    const s = texto(t).trim();
    if (s === "") return null;
    const x = numero(s);
    return Number.isFinite(x) ? x : s;
  };
  function serializar() {
    const grupo = (g) => Object.fromEntries(Object.entries(g || {}).map(([k, v]) => [k, num(v)]));
    return {
      formato: FORMATO,
      versao: VERSAO,
      nome: p.nome,
      cota: num(p.cota),
      banco_duplo: Boolean(p.banco_duplo),
      casos: p.casos.map((c) => ({
        caso_id: c.caso_id,
        carcaca: c.carcaca,
        motor_id: c.motor_id,
        R_min: num(c.R_min),
        R_max: num(c.R_max),
        R2_min: num(c.R2_min),
        R2_max: num(c.R2_max),
        ajustes: { chapa: grupo(c.ajustes?.chapa), motor: grupo(c.ajustes?.motor) },
      })),
    };
  }
  function normalizar(obj) {
    if (!obj || obj.formato !== FORMATO) throw new Error("arquivo não é um projeto do tensorcad");
    if (obj.versao !== VERSAO) throw new Error(`versão de projeto não suportada: ${obj.versao}`);
    if (!Array.isArray(obj.casos) || obj.casos.length === 0) throw new Error("projeto sem casos");
    const grupo = (g) => Object.fromEntries(Object.entries(g || {}).map(([k, v]) => [k, texto(v)]));
    return {
      formato: FORMATO,
      versao: VERSAO,
      nome: texto(obj.nome) || "PROJETO",
      cota: texto(obj.cota),
      banco_duplo: Boolean(obj.banco_duplo),
      ativo: Math.min(Math.max(0, Number(obj.ativo) || 0), obj.casos.length - 1),
      casos: obj.casos.map((c, i) => ({
        caso_id: texto(c.caso_id) || `caso-${i + 1}`,
        carcaca: texto(c.carcaca),
        motor_id: c.motor_id || null,
        R_min: texto(c.R_min),
        R_max: texto(c.R_max),
        R2_min: texto(c.R2_min),
        R2_max: texto(c.R2_max),
        ajustes: { chapa: grupo(c.ajustes?.chapa), motor: grupo(c.ajustes?.motor) },
        _status: "",
      })),
    };
  }

  // ---------------------------------------------------------------- rascunho
  function agendarRascunho() {
    clearTimeout(timerRascunho);
    timerRascunho = setTimeout(() => {
      try {
        localStorage.setItem(CHAVE_RASCUNHO, JSON.stringify({ ...serializar(), ativo: p.ativo }));
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
    aviso(`projeto salvo: ${nomeArquivo()}.json (${p.casos.length} caso(s))`);
  }

  async function abrirArquivo(arquivo) {
    try {
      const obj = normalizar(JSON.parse(await arquivo.text()));
      p = obj;
      carregarNoFormulario();
      atualizarStatusTodos();
      aviso(`projeto aberto: ${p.nome} (${p.casos.length} caso(s))`);
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
          const m = /^casos\[(\d+)\]\.(.*)$/.exec(k);
          return m ? `${p.casos[Number(m[1])].caso_id}: ${m[2]} — ${v}` : `${k}: ${v}`;
        });
        aviso(`Exportação recusada:\n${linhas.join("\n") || d.erro}`, "erro", 9000);
        return;
      }
      baixar(await r.blob(), `${nomeArquivo()}.xlsx`);
      aviso(`planilha exportada: ${nomeArquivo()}.xlsx (${p.casos.length} caso(s), uma aba cada)`);
    } catch (e) {
      aviso(`Erro ao exportar: ${e.message}`, "erro", 7000);
    }
  }

  async function atualizarStatusTodos() {
    const cota = p.cota;
    for (const [i, c] of p.casos.entries()) {
      if (i === p.ativo) continue;
      if (!c.R_min || !c.R_max) continue;
      try {
        const r = await obter("/api/calcular", {
          method: "POST",
          body: JSON.stringify({ ...c, cota: cota || null }),
        });
        c._status = r.status;
      } catch (_e) {
        c._status = "ERRO";
      }
    }
    renderLista();
  }

  function limpar() {
    lerFormulario();
    const n = p.casos.length;
    const msg =
      `Limpar a memória?\n\nOs ${n} caso(s) do projeto "${p.nome}" serão apagados deste navegador.\n` +
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
    carregarNoFormulario();
    if (rascunho) {
      aviso(`rascunho restaurado: ${p.nome} (${p.casos.length} caso(s))`);
      atualizarStatusTodos();
    }
  }

  return { iniciar, lerFormulario, errosLocais, definirStatus, serializar, estado: () => p };
})();
