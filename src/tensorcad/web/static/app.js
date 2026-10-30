"use strict";
// tensorcad — interface web: projeto com vários casos (W4), campos e cálculo ao vivo (W1),
// dimensões editáveis (W3) e desenho (desenho.js, W2).

const ROTULO = { ok: "OK", parcial: "PARCIAL", erro: "ERRO" };
const ESPERA_MS = 300;
const estado = {
  carcacas: [],
  timer: null,
  controle: null,
  campos: { chapa: [], motor: [] },
  padrao: { chapa: {}, motor: {} },
  ajustes: { chapa: {}, motor: {} },
};
const OPCIONAIS = new Set(["comprimento_ranhura", "dist_entre_ranhuras", "largura_ranhura"]);

const $ = (id) => document.getElementById(id);
const fmt = (v, casas = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

async function obter(caminho, opcoes = {}) {
  const r = await fetch(caminho, { headers: { Accept: "application/json", "Content-Type": "application/json" }, ...opcoes });
  const dados = await r.json();
  if (!r.ok) {
    const erro = new Error(dados.erro || `HTTP ${r.status}`);
    erro.campos = dados.erros || {};
    throw erro;
  }
  return dados;
}

function definirConexao(est, texto) {
  const el = $("conexao");
  el.dataset.estado = est;
  el.textContent = texto;
}

// ------------------------------------------------------------------ carcaças e motores

function preencherCarcacas(lista) {
  estado.carcacas = lista;
  const ul = $("lista-carcacas");
  const sel = $("carcaca");
  ul.replaceChildren();
  sel.replaceChildren();
  for (const c of lista) {
    const li = document.createElement("li");
    li.dataset.carcaca = c.carcaca;
    li.dataset.status = c.status;
    li.title = c.detalhe;
    const nome = document.createElement("span");
    nome.textContent = `${c.carcaca}  (${c.motores.map((m) => m.carcaca).join(", ") || "sem motor"})`;
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.dataset.status = c.status;
    chip.textContent = ROTULO[c.status] || c.status;
    li.append(nome, chip);
    li.addEventListener("click", () => {
      if (!c.calculavel) return;
      sel.value = c.carcaca;
      aoTrocarCarcaca();
    });
    ul.append(li);

    const op = document.createElement("option");
    op.value = c.carcaca;
    op.textContent = `● ${c.carcaca} — ${ROTULO[c.status] || c.status}`;
    op.dataset.status = c.status;
    op.disabled = !c.calculavel;
    sel.append(op);
  }
  const primeira = lista.find((c) => c.calculavel);
  sel.disabled = !primeira;
  if (primeira) sel.value = primeira.carcaca;
  aoTrocarCarcaca();
}

function carcacaAtual() {
  return estado.carcacas.find((c) => c.carcaca === $("carcaca").value);
}

function aoTrocarCarcaca(_ev = null, { manterAjustes = false, motorId = null } = {}) {
  const c = carcacaAtual();
  $("carcaca").dataset.status = c ? c.status : "";
  $("carcaca-detalhe").textContent = c ? c.detalhe : "";
  for (const li of $("lista-carcacas").children) li.classList.toggle("ativa", c && li.dataset.carcaca === c.carcaca);
  const selM = $("motor_id");
  selM.replaceChildren();
  for (const m of c ? c.motores : []) {
    const op = document.createElement("option");
    op.value = m.motor_id;
    op.textContent = `${m.motor_id}  (eixo ${m.H} · A ${m.A} · K ${m.K})`;
    selM.append(op);
  }
  selM.disabled = !c || c.motores.length === 0;
  if (motorId && c && c.motores.some((m) => m.motor_id === motorId)) selM.value = motorId;
  estado.padrao.chapa = (c && c.dimensoes_chapa) || {};
  if (!manterAjustes) estado.ajustes = { chapa: {}, motor: {} };
  montarDimensoes("chapa");
  aoTrocarMotor(null, { manterAjustes });
}

function aoTrocarMotor(_ev = null, { manterAjustes = false } = {}) {
  const c = carcacaAtual();
  const m = c && c.motores.find((x) => x.motor_id === $("motor_id").value);
  estado.padrao.motor = m ? { H: m.H, A: m.A, K: m.K } : {};
  if (!manterAjustes) estado.ajustes.motor = {};
  montarDimensoes("motor");
  agendarCalculo();
}

// ------------------------------------------------------------------ dimensões (W3)

const numero = (t) => (t === "" || t === null || t === undefined ? null : Number(String(t).replace(",", ".")));

function montarDimensoes(grupo) {
  const caixa = $(grupo === "chapa" ? "dims-chapa" : "dims-motor");
  caixa.replaceChildren();
  for (const meta of estado.campos[grupo]) {
    const padrao = estado.padrao[grupo][meta.campo];
    const div = document.createElement("div");
    div.className = "dim campo";
    div.dataset.campo = `ajustes.${grupo}.${meta.campo}`;
    div.dataset.grupo = grupo;
    div.dataset.nome = meta.campo;
    const id = `dim-${grupo}-${meta.campo}`;
    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = `${meta.rotulo} (${meta.unidade})`;
    const peq = document.createElement("small");
    peq.textContent = `padrão: ${padrao === null || padrao === undefined ? "—" : fmt(padrao, padrao % 1 ? 2 : 0)}`;
    label.append(peq);
    const inp = document.createElement("input");
    inp.id = id;
    inp.inputMode = "decimal";
    const atual = meta.campo in estado.ajustes[grupo] ? estado.ajustes[grupo][meta.campo] : padrao;
    inp.value = atual === null || atual === undefined ? "" : String(atual);
    inp.placeholder = OPCIONAIS.has(meta.campo) ? "vazio" : "";
    inp.addEventListener("input", () => aoEditarDimensao(grupo, meta.campo, inp.value));
    const rest = document.createElement("button");
    rest.type = "button";
    rest.className = "restaurar";
    rest.title = "restaurar o padrão";
    rest.textContent = "↺";
    rest.addEventListener("click", () => {
      inp.value = padrao === null || padrao === undefined ? "" : String(padrao);
      aoEditarDimensao(grupo, meta.campo, inp.value);
    });
    const erro = document.createElement("p");
    erro.className = "erro-campo";
    div.append(label, inp, rest, erro);
    caixa.append(div);
  }
  $("painel-dimensoes").hidden = estado.campos.chapa.length === 0;
  atualizarAjustes();
}

function aoEditarDimensao(grupo, campo, texto) {
  const padrao = estado.padrao[grupo][campo];
  const t = texto.trim();
  const igual = t === "" ? padrao === null || padrao === undefined : numero(t) === padrao;
  if (igual) delete estado.ajustes[grupo][campo];
  else estado.ajustes[grupo][campo] = t;
  atualizarAjustes();
  agendarCalculo();
}

function atualizarAjustes() {
  let n = 0;
  for (const div of document.querySelectorAll(".dim")) {
    const alterado = div.dataset.nome in estado.ajustes[div.dataset.grupo];
    div.classList.toggle("alterado", alterado);
    n += alterado ? 1 : 0;
  }
  const cont = $("contagem-ajustes");
  cont.hidden = n === 0;
  cont.textContent = `${n} alterad${n === 1 ? "a" : "as"}`;
  $("btn-restaurar-tudo").disabled = n === 0;
  atualizarSoma();
}

function valorChapa(campo) {
  const aj = estado.ajustes.chapa;
  return campo in aj ? numero(aj[campo]) : estado.padrao.chapa[campo] ?? null;
}

function atualizarSoma() {
  const el = $("soma-cotas");
  const [c, l, tam, vao, topo] = ["comprimento_chapa", "dist_L_ranhura", "comprimento_ranhura",
    "dist_entre_ranhuras", "dist_ranhura_topo"].map(valorChapa);
  el.className = "soma-cotas";
  if ([c, l, topo].some((v) => v === null || Number.isNaN(v))) {
    el.textContent = "";
    return;
  }
  if (tam === null || vao === null || Number.isNaN(tam) || Number.isNaN(vao)) {
    el.textContent = `pontas: ${fmt(l, 0)} … ${fmt(topo, 0)} (comprimento ${fmt(c, 0)}; ranhura ou vão deduzido)`;
    return;
  }
  const soma = l + 2 * tam + vao + topo;
  const fecha = Math.abs(soma - c) <= 0.5;
  el.classList.add(fecha ? "ok" : "erro");
  el.textContent = `${fmt(l, 0)} + 2×${fmt(tam, 0)} + ${fmt(vao, 0)} + ${fmt(topo, 0)} = ${fmt(soma, 1)} ${fecha ? "✓" : "≠"} ${fmt(c, 0)}`;
}

function restaurarTudo() {
  estado.ajustes = { chapa: {}, motor: {} };
  montarDimensoes("chapa");
  montarDimensoes("motor");
  agendarCalculo();
}

// ------------------------------------------------------------------ cálculo ao vivo

function lerCampos() {
  return {
    caso_id: $("caso_id").value.trim() || "caso",
    carcaca: $("carcaca").value,
    motor_id: $("motor_id").value || null,
    R_min: $("R_min").value.trim(),
    R_max: $("R_max").value.trim(),
    cota: $("cota").value.trim() || null,
    ajustes: estado.ajustes,
    banco_duplo: {
      // ligado sem nenhum R2 preenchido: calcula só o banco 1 (e pede os raios)
      ativo: $("banco-duplo").checked && Boolean($("R2_min").value.trim() || $("R2_max").value.trim()),
      R2_min: $("R2_min").value.trim(),
      R2_max: $("R2_max").value.trim(),
    },
  };
}

// ------------------------------------------------------------------ banco duplo

function mostrarBancoDuplo() {
  const ativo = $("banco-duplo").checked;
  for (const el of document.querySelectorAll(".so-banco2")) el.hidden = !ativo;
}

function mostrarBanco2(b) {
  const tbody = $("banco2").querySelector("tbody");
  tbody.replaceChildren();
  $("banco2-mensagem").textContent = b
    ? b.ok
      ? "motor entre os arcos R1 e R2 nas duas tensões"
      : b.avisos.join("\n")
    : $("banco-duplo").checked
      ? "preencha R2min e R2max"
      : "";
  if (!b) return;
  for (const q of b.posicoes) {
    const tr = document.createElement("tr");
    for (const t of [`${q.rotulo} %`, fmt(q.dist_O2), fmt(q.R2, 0), fmt(q.curso)]) {
      const td = document.createElement("td");
      td.textContent = t;
      tr.append(td);
    }
    tr.lastChild.classList.toggle("neg", !q.dentro);
    const td = document.createElement("td");
    const ponto = document.createElement("span");
    ponto.className = "ponto";
    ponto.dataset.status = q.dentro ? "OK" : "AVISO";
    ponto.title = q.dentro ? "há trecho entre o arco R1 e o arco R2" : "sem trecho entre o arco R1 e o arco R2";
    td.append(ponto);
    tr.append(td);
    tbody.append(tr);
  }
}

function marcarErros(erros) {
  $("erro-dimensoes").textContent = erros["ajustes.chapa"] || erros["ajustes.motor"] || "";
  for (const div of document.querySelectorAll("#form-caso .campo")) {
    const msg = erros[div.dataset.campo];
    div.classList.toggle("invalido", Boolean(msg));
    const p = div.querySelector(".erro-campo");
    if (p) p.textContent = msg || "";
  }
}

function agendarCalculo() {
  Projeto.lerFormulario();
  clearTimeout(estado.timer);
  estado.timer = setTimeout(calcular, ESPERA_MS);
}

async function calcular() {
  const campos = lerCampos();
  if (!campos.R_min || !campos.R_max || !campos.carcaca) {
    Projeto.definirStatus("");
    marcarErros(Projeto.errosLocais());
    mostrarVazio("preencha Rmin e Rmax");
    return;
  }
  if (estado.controle) estado.controle.abort();
  estado.controle = new AbortController();
  $("status").classList.add("calculando");
  try {
    const r = await obter("/api/calcular", {
      method: "POST",
      body: JSON.stringify(campos),
      signal: estado.controle.signal,
    });
    marcarErros(Projeto.errosLocais());
    Projeto.definirStatus(r.status);
    mostrarResultado(r);
    const trocou = estado.ultimaCarcaca !== campos.carcaca;
    estado.ultimaCarcaca = campos.carcaca;
    Desenho.desenhar(r.desenho, { reajustar: trocou });
    $("info-desenho").textContent = r.desenho
      ? `desenho em H = ${fmt(r.desenho.H)} (${r.cota_informada !== null ? "informada" : "recomendada"})`
      : "";
  } catch (e) {
    if (e.name === "AbortError") return;
    Projeto.definirStatus("ERRO");
    marcarErros({ ...(e.campos || {}), ...Projeto.errosLocais() });
    mostrarVazio(Object.keys(e.campos || {}).length ? "corrija os campos destacados" : `Erro: ${e.message}`);
  } finally {
    $("status").classList.remove("calculando");
  }
}

function linhaResumo(dl, rotulo, valor, destaque = false) {
  const div = document.createElement("div");
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = rotulo;
  dd.textContent = valor;
  if (destaque) dd.classList.add("destaque");
  div.append(dt, dd);
  dl.append(div);
}

function mostrarVazio(texto) {
  Desenho.desenhar(null);
  $("info-desenho").textContent = "";
  const st = $("status");
  st.dataset.status = "";
  st.textContent = texto;
  $("mensagem").textContent = "";
  $("resumo").replaceChildren();
  $("chapa-info").replaceChildren();
  $("posicoes").querySelector("tbody").replaceChildren();
  mostrarBanco2(null);
}

function mostrarResultado(r) {
  const st = $("status");
  st.dataset.status = r.status;
  st.textContent = r.status.replace("_", " ");
  $("mensagem").textContent = r.mensagem;

  const resumo = $("resumo");
  resumo.replaceChildren();
  const faixas = r.faixas_cota.length
    ? r.faixas_cota.map(([a, b]) => `${fmt(a)} a ${fmt(b)}`).join("; ")
    : "nenhuma";
  linhaResumo(resumo, "Faixa admissível de H", faixas);
  linhaResumo(resumo, "H recomendada", fmt(r.cota_recomendada), true);
  linhaResumo(resumo, "Folga mínima na recomendada", fmt(r.margem_recomendada));
  if (r.em_informada) {
    const m = Math.min(...r.em_informada.map((p) => (p.margem ?? -Infinity)));
    linhaResumo(resumo, `Folga mínima em H = ${fmt(r.cota_informada)}`, fmt(m));
  }

  const tbody = $("posicoes").querySelector("tbody");
  tbody.replaceChildren();
  for (const [rotulo, par] of [["rec", r.em_recomendada], ["inf", r.em_informada]]) {
    if (!par) continue;
    par.forEach((p, i) => {
      const tr = document.createElement("tr");
      tr.dataset.tipo = rotulo;
      const celulas = [
        fmt(p.cota, 0),
        i === 0 ? "0 %" : "3 %",
        fmt(p.d_motor),
        fmt(p.folga_neg),
        fmt(p.folga_pos),
      ];
      celulas.forEach((t, j) => {
        const td = document.createElement("td");
        td.textContent = t;
        if (j === 0) {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = rotulo;
          tag.title = rotulo === "rec" ? "H recomendada" : "H informada";
          td.prepend(tag);
        }
        if ((j === 3 && p.folga_neg < 0) || (j === 4 && p.folga_pos < 0)) td.classList.add("neg");
        tr.append(td);
      });
      const td = document.createElement("td");
      const ponto = document.createElement("span");
      ponto.className = "ponto";
      ponto.dataset.status = p.status;
      ponto.title = [p.status, ...p.mensagens].join("\n");
      td.append(ponto);
      tr.append(td);
      tbody.append(tr);
    });
  }

  const info = $("chapa-info");
  info.replaceChildren();
  linhaResumo(info, "Chapa", `${r.chapa.chapa_id} (${r.chapa.origem})`);
  linhaResumo(info, "Comprimento / inclinação", `${fmt(r.chapa.comprimento, 0)} mm · ${fmt(r.chapa.theta_deg, 0)}°`);
  linhaResumo(info, "Tubo → L (dx / dy)", `${fmt(r.chapa.dx_L_tubo)} / ${fmt(r.chapa.dy_L_tubo)}`);
  linhaResumo(info, "Motor / h sobre a chapa", `${r.motor.motor_id} · ${fmt(r.h, 0)}`);
  mostrarBanco2(r.banco_duplo);
}

// ------------------------------------------------------------------ início

async function iniciar() {
  Desenho.iniciar();
  for (const id of ["cota", "caso_id", "R_min", "R_max", "nome-projeto", "R2_min", "R2_max"]) {
    $(id).addEventListener("input", agendarCalculo);
  }
  $("banco-duplo").addEventListener("change", () => {
    mostrarBancoDuplo();
    agendarCalculo();
  });
  $("carcaca").addEventListener("change", aoTrocarCarcaca);
  $("motor_id").addEventListener("change", aoTrocarMotor);
  $("btn-restaurar-tudo").addEventListener("click", (ev) => {
    ev.preventDefault();
    restaurarTudo();
  });
  $("form-caso").addEventListener("submit", (ev) => ev.preventDefault());

  try {
    const s = await obter("/api/saude");
    $("versao").textContent = `v${s.versao}`;
    const fonte = $("fonte-dados");
    fonte.textContent = `dados: ${s.dados}`;
    fonte.title = `cadastros: ${s.dados}\nchapas: ${s.padroes}\navisos: ${s.avisos}\nerros na tabela de chapas: ${s.erros_chapas}\nfaixa: ${s.faixa.join("–")}`;
    $("fixo-x-tubo").textContent = fmt(s.fixos.x_tubo, 0);
    $("fixo-y-piso").textContent = fmt(s.fixos.y_piso, 0);
    $("fixo-dy-banco2").textContent = fmt(s.fixos.dy_banco2, 0);
    definirConexao("ok", "conectado");
    estado.campos = await obter("/api/campos");
    preencherCarcacas(await obter("/api/carcacas"));
    Projeto.iniciar();
  } catch (e) {
    definirConexao("erro", "sem conexão");
    mostrarVazio(`Erro: ${e.message}`);
  }

}

document.addEventListener("DOMContentLoaded", iniciar);
