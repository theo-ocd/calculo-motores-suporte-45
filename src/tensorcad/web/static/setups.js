"use strict";
// tensorcad — setups de transmissão (S3): biblioteca no navegador, formulário com as
// listas (polias, rpm WEG 60 Hz), cálculo no servidor (/api/setup) e arquivo próprio
// (formato tensorcad-setups v1), reaproveitável entre projetos.
// Usa os globais de app.js ($, obter, fmt, numero) e Projeto (casos a partir de setups).

const Setups = (() => {
  const FORMATO = "tensorcad-setups";
  const VERSAO = 1;
  const CHAVE = "tensorcad.setups.v1";
  let lista = []; // setups calculados (como devolvidos por /api/setup, com id)
  let ativo = -1; // índice em edição; -1 = novo
  let listas = { polia_maquina: [], polia_motor: [], rpm_motor: [] };
  let timer = null;
  let ultimo = null; // último cálculo válido do formulário

  const novoId = () =>
    (crypto.randomUUID ? crypto.randomUUID() : `s${Date.now()}${Math.random().toString(16).slice(2)}`);
  const porId = (id) => lista.find((s) => s.id === id) || null;

  // ---------------------------------------------------------------- persistência
  function gravar() {
    try {
      localStorage.setItem(CHAVE, JSON.stringify({ formato: FORMATO, versao: VERSAO, setups: lista }));
    } catch (_e) {
      /* armazenamento indisponível */
    }
    aoMudar();
  }
  function ler() {
    try {
      const d = JSON.parse(localStorage.getItem(CHAVE) || "null");
      return d && d.formato === FORMATO && Array.isArray(d.setups) ? d.setups : [];
    } catch (_e) {
      return [];
    }
  }
  function aoMudar() {
    renderLista();
    renderLayout();
    if (typeof Projeto !== "undefined" && Projeto.estado()) Projeto.verificarSetup();
  }

  // ---------------------------------------------------------------- formulário
  function opcoes(sel, valores, sufixo = "") {
    sel.replaceChildren();
    for (const v of valores) {
      const op = document.createElement("option");
      op.value = String(v);
      op.textContent = `${fmt(v, 0)}${sufixo}`;
      sel.append(op);
    }
  }
  function lerForm() {
    const b2 = $("setup-banco2").checked;
    return {
      id: ativo >= 0 ? lista[ativo].id : null,
      nome: $("setup-nome").value.trim(),
      polia_maquina: $("setup-polia-maquina").value,
      polia_motor: $("setup-polia-motor").value,
      correia: $("setup-correia").value.trim(),
      rpm_motor: $("setup-rpm").value,
      banco2: b2
        ? {
            polia_maquina: $("setup2-polia-maquina").value,
            polia_motor: $("setup2-polia-motor").value,
            correia: $("setup2-correia").value.trim(),
          }
        : null,
    };
  }
  function carregarForm(s) {
    $("setup-nome").value = s ? s.nome : "";
    const val = (sel, v, padrao) => {
      $(sel).value = String(v ?? padrao);
    };
    val("setup-polia-maquina", s?.polia_maquina, listas.polia_maquina[0]);
    val("setup-polia-motor", s?.polia_motor, 170);
    $("setup-correia").value = s ? String(s.correia) : "";
    val("setup-rpm", s?.rpm_motor, 1200);
    $("setup-banco2").checked = Boolean(s && s.banco2);
    val("setup2-polia-maquina", s?.banco2?.polia_maquina, listas.polia_maquina[0]);
    val("setup2-polia-motor", s?.banco2?.polia_motor, 170);
    $("setup2-correia").value = s?.banco2 ? String(s.banco2.correia) : "";
    $("setup-campos-banco2").hidden = !$("setup-banco2").checked;
    agendar();
  }
  function marcar(erros) {
    for (const div of document.querySelectorAll("#form-setup .campo")) {
      const msg = erros[div.dataset.campo];
      div.classList.toggle("invalido", Boolean(msg));
      const p = div.querySelector(".erro-campo");
      if (p) p.textContent = msg || "";
    }
  }
  function errosLocais(s) {
    if (!s.nome) return { nome: "o setup precisa de um nome" };
    const outro = lista.findIndex((x) => x.nome.toLowerCase() === s.nome.toLowerCase());
    return outro >= 0 && outro !== ativo ? { nome: "já existe um setup com este nome" } : {};
  }

  // ---------------------------------------------------------------- cálculo
  function agendar() {
    clearTimeout(timer);
    timer = setTimeout(calcular, 200);
  }
  async function calcular() {
    const s = lerForm();
    ultimo = null;
    if (!s.correia || (s.banco2 && !s.banco2.correia)) {
      marcar(errosLocais(s));
      mostrar(null, "preencha o comprimento da correia");
      return;
    }
    try {
      const r = await obter("/api/setup", { method: "POST", body: JSON.stringify({ ...s, nome: s.nome || "—" }) });
      r.nome = s.nome;
      ultimo = r;
      marcar(errosLocais(s));
      mostrar(r);
    } catch (e) {
      marcar({ ...(e.campos || {}), ...errosLocais(s) });
      mostrar(null, Object.keys(e.campos || {}).length ? "corrija os campos destacados" : `Erro: ${e.message}`);
    }
  }
  function linha(dl, rot, val, destaque = false) {
    const dt = document.createElement("dt");
    dt.textContent = rot;
    const dd = document.createElement("dd");
    dd.textContent = val;
    if (destaque) dd.classList.add("destaque");
    dl.append(dt, dd);
  }
  function mostrar(r, msg = "") {
    const st = $("setup-status");
    const dl = $("setup-resumo");
    dl.replaceChildren();
    if (!r) {
      st.dataset.status = "";
      st.textContent = msg;
      return;
    }
    st.dataset.status = "OK";
    st.textContent = `${r.nome || "(sem nome)"}${r.sufixo}`;
    linha(dl, "Sufixo do caso", r.sufixo, true);
    linha(dl, "R_min (0 %)", fmt(r.R_min), true);
    linha(dl, "R a 2 % (referência)", fmt(r.R_info));
    linha(dl, "R_max (3 %)", fmt(r.R_max), true);
    linha(dl, "rpm da máquina", fmt(r.rpm_maquina, 1));
    if (r.banco2) {
      linha(dl, "R2_min (0 %), banco 2", fmt(r.banco2.R2_min), true);
      linha(dl, "R2 a 2 %, banco 2", fmt(r.banco2.R2_info));
      linha(dl, "R2_max (3 %), banco 2", fmt(r.banco2.R2_max), true);
      linha(dl, "rpm da máquina, banco 2", fmt(r.banco2.rpm_maquina, 1));
    }
  }

  // ---------------------------------------------------------------- biblioteca
  async function salvar() {
    // recalcula agora: o cálculo agendado pode ainda não ter rodado com os últimos valores
    clearTimeout(timer);
    await calcular();
    const s = lerForm();
    const erros = errosLocais(s);
    if (Object.keys(erros).length || !ultimo) {
      marcar(erros);
      Projeto.aviso("Corrija o setup antes de salvar.", "erro");
      return;
    }
    const novo = { ...ultimo, nome: s.nome, id: s.id || novoId() };
    if (ativo >= 0) lista[ativo] = novo;
    else {
      lista.push(novo);
      ativo = lista.length - 1;
    }
    gravar();
    Projeto.aviso(`setup salvo: ${novo.nome}${novo.sufixo}`);
  }
  function selecionar(i) {
    ativo = i;
    ultimo = null;
    carregarForm(i >= 0 ? lista[i] : null);
    renderLista();
  }
  function novo() {
    selecionar(-1);
    $("setup-nome").focus();
  }
  function duplicar() {
    if (ativo < 0) return;
    const base = lista[ativo];
    let nome = `${base.nome}-copia`;
    for (let k = 2; lista.some((x) => x.nome.toLowerCase() === nome.toLowerCase()); k++) nome = `${base.nome}-copia-${k}`;
    lista.push({ ...JSON.parse(JSON.stringify(base)), id: novoId(), nome });
    gravar();
    selecionar(lista.length - 1);
  }
  function excluir() {
    if (ativo < 0) return;
    if (!window.confirm(`Excluir o setup "${lista[ativo].nome}" da biblioteca? Os casos já criados ficam como estão.`)) return;
    lista.splice(ativo, 1);
    gravar();
    selecionar(Math.min(ativo, lista.length - 1));
  }
  function salvarArquivo() {
    const blob = new Blob([JSON.stringify({ formato: FORMATO, versao: VERSAO, setups: lista }, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "setups.json";
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    Projeto.aviso(`biblioteca salva: setups.json (${lista.length} setup(s))`);
  }
  async function abrirArquivo(arquivo) {
    try {
      const d = await obter("/api/biblioteca", { method: "POST", body: await arquivo.text() });
      let novos = 0;
      for (const s of d.setups) {
        const s2 = { ...s, id: s.id || novoId() };
        const i = lista.findIndex((x) => x.id === s2.id || x.nome.toLowerCase() === s2.nome.toLowerCase());
        if (i >= 0) lista[i] = { ...s2, id: lista[i].id };
        else {
          lista.push(s2);
          novos += 1;
        }
      }
      gravar();
      selecionar(lista.length ? 0 : -1);
      Projeto.aviso(`biblioteca aberta: ${d.setups.length} setup(s), ${novos} novo(s); os de mesmo nome foram substituídos`);
    } catch (e) {
      const det = Object.entries(e.campos || {}).map(([k, v]) => `${k}: ${v}`).join("\n");
      Projeto.aviso(`Não foi possível abrir a biblioteca: ${det || e.message}`, "erro", 8000);
    }
  }

  // ---------------------------------------------------------------- listas
  const resumo = (s) => `Ø${fmt(s.polia_motor, 0)} · ${fmt(s.correia, 0)} · ${fmt(s.R_min, 0)}/${fmt(s.R_max, 0)}${s.banco2 ? " · B2" : ""}`;
  function renderLista() {
    const ul = $("lista-setups");
    ul.replaceChildren();
    lista.forEach((s, i) => {
      const li = document.createElement("li");
      li.dataset.indice = i;
      li.classList.toggle("ativo", i === ativo);
      const ponto = document.createElement("span");
      ponto.className = "ponto";
      ponto.dataset.status = "OK";
      const nome = document.createElement("span");
      nome.className = "nome-caso";
      nome.textContent = `${s.nome}${s.sufixo}`;
      const info = document.createElement("span");
      info.className = "info-caso";
      info.textContent = resumo(s);
      li.append(ponto, nome, info);
      li.addEventListener("click", () => selecionar(i));
      ul.append(li);
    });
    $("contagem-setups").textContent = `(${lista.length})`;
    $("btn-setup-excluir").disabled = ativo < 0;
    $("btn-setup-duplicar").disabled = ativo < 0;
  }
  function renderLayout() {
    const ul = $("lista-setups-layout");
    ul.replaceChildren();
    if (!lista.length) {
      const li = document.createElement("li");
      li.className = "dica";
      li.textContent = "nenhum setup salvo";
      ul.append(li);
      return;
    }
    for (const s of lista) {
      const li = document.createElement("li");
      li.dataset.setup = s.id;
      const nome = document.createElement("span");
      nome.innerHTML = "";
      nome.textContent = `${s.nome}${s.sufixo}`;
      const info = document.createElement("span");
      info.className = "info-caso";
      info.textContent = ` ${resumo(s)}`;
      nome.append(info);
      const b = document.createElement("button");
      b.type = "button";
      b.className = "botao-mini";
      b.textContent = "+ caso";
      b.title = "criar um caso deste setup no layout ativo (R e sufixo travados)";
      b.addEventListener("click", () => Projeto.casoDeSetup(s));
      li.append(nome, b);
      ul.append(li);
    }
  }

  // ---------------------------------------------------------------- abas
  function mostrarAba(aba) {
    document.body.dataset.aba = aba;
    for (const b of document.querySelectorAll(".abas button")) b.classList.toggle("ativa", b.dataset.aba === aba);
  }

  async function iniciar() {
    listas = await obter("/api/transmissao");
    for (const pre of ["setup", "setup2"]) {
      opcoes($(`${pre}-polia-maquina`), listas.polia_maquina);
      opcoes($(`${pre}-polia-motor`), listas.polia_motor);
    }
    opcoes($("setup-rpm"), listas.rpm_motor, " rpm");
    lista = ler();
    for (const id of ["setup-nome", "setup-correia", "setup2-correia"]) $(id).addEventListener("input", agendar);
    for (const id of ["setup-polia-maquina", "setup-polia-motor", "setup-rpm", "setup2-polia-maquina", "setup2-polia-motor"]) {
      $(id).addEventListener("change", agendar);
    }
    $("setup-banco2").addEventListener("change", () => {
      $("setup-campos-banco2").hidden = !$("setup-banco2").checked;
      agendar();
    });
    $("btn-setup-salvar").addEventListener("click", salvar);
    $("btn-setup-novo").addEventListener("click", novo);
    $("btn-setup-duplicar").addEventListener("click", duplicar);
    $("btn-setup-excluir").addEventListener("click", excluir);
    $("btn-biblioteca-salvar").addEventListener("click", salvarArquivo);
    $("btn-biblioteca-abrir").addEventListener("click", () => $("arquivo-biblioteca").click());
    $("arquivo-biblioteca").addEventListener("change", (ev) => {
      const f = ev.target.files[0];
      ev.target.value = "";
      if (f) abrirArquivo(f);
    });
    $("form-setup").addEventListener("submit", (ev) => ev.preventDefault());
    for (const b of document.querySelectorAll(".abas button")) b.addEventListener("click", () => mostrarAba(b.dataset.aba));
    mostrarAba("layout");
    selecionar(lista.length ? 0 : -1);
    renderLayout();
  }

  return { iniciar, porId, lista: () => lista, mostrarAba };
})();
