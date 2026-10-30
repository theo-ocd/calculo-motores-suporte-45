"use strict";
// tensorcad — interface web. W1: seletor de carcaça, campos e cálculo ao vivo.

const ROTULO = { ok: "OK", parcial: "PARCIAL", erro: "ERRO" };
const ESPERA_MS = 300;
const estado = { carcacas: [], timer: null, controle: null };

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

function aoTrocarCarcaca() {
  const c = carcacaAtual();
  $("carcaca").dataset.status = c ? c.status : "";
  $("carcaca-detalhe").textContent = c ? c.detalhe : "";
  for (const li of $("lista-carcacas").children) li.classList.toggle("ativa", c && li.dataset.carcaca === c.carcaca);
  const selM = $("motor_id");
  selM.replaceChildren();
  for (const m of c ? c.motores : []) {
    const op = document.createElement("option");
    op.value = m.motor_id;
    op.textContent = `${m.motor_id}  (H ${m.H} · A ${m.A} · K ${m.K})`;
    selM.append(op);
  }
  selM.disabled = !c || c.motores.length === 0;
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
  };
}

function marcarErros(erros) {
  for (const div of document.querySelectorAll("#form-caso .campo")) {
    const msg = erros[div.dataset.campo];
    div.classList.toggle("invalido", Boolean(msg));
    const p = div.querySelector(".erro-campo");
    if (p) p.textContent = msg || "";
  }
}

function agendarCalculo() {
  clearTimeout(estado.timer);
  estado.timer = setTimeout(calcular, ESPERA_MS);
}

async function calcular() {
  const campos = lerCampos();
  if (!campos.R_min || !campos.R_max || !campos.carcaca) {
    marcarErros({});
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
    marcarErros({});
    mostrarResultado(r);
  } catch (e) {
    if (e.name === "AbortError") return;
    marcarErros(e.campos || {});
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
  const st = $("status");
  st.dataset.status = "";
  st.textContent = texto;
  $("mensagem").textContent = "";
  $("resumo").replaceChildren();
  $("chapa-info").replaceChildren();
  $("posicoes").querySelector("tbody").replaceChildren();
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
  linhaResumo(resumo, "Faixa admissível da cota 1646", faixas);
  linhaResumo(resumo, "Cota 1646 recomendada", fmt(r.cota_recomendada), true);
  linhaResumo(resumo, "Folga mínima na recomendada", fmt(r.margem_recomendada));
  if (r.em_informada) {
    const m = Math.min(...r.em_informada.map((p) => (p.margem ?? -Infinity)));
    linhaResumo(resumo, `Folga mínima na cota ${fmt(r.cota_informada)}`, fmt(m));
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
          tag.title = rotulo === "rec" ? "cota recomendada" : "cota informada";
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
  linhaResumo(info, "Motor / h", `${r.motor.motor_id} · h ${fmt(r.h, 0)}`);
}

// ------------------------------------------------------------------ início

async function iniciar() {
  for (const id of ["cota", "caso_id", "R_min", "R_max"]) $(id).addEventListener("input", agendarCalculo);
  $("carcaca").addEventListener("change", aoTrocarCarcaca);
  $("motor_id").addEventListener("change", agendarCalculo);
  $("form-caso").addEventListener("submit", (ev) => ev.preventDefault());

  try {
    const s = await obter("/api/saude");
    $("versao").textContent = `v${s.versao}`;
    const fonte = $("fonte-dados");
    fonte.textContent = `dados: ${s.dados}`;
    fonte.title = `cadastros: ${s.dados}\nchapas: ${s.padroes}\navisos: ${s.avisos}\nerros na tabela de chapas: ${s.erros_chapas}\nfaixa: ${s.faixa.join("–")}`;
    $("fixo-x-tubo").textContent = fmt(s.fixos.x_tubo, 0);
    $("fixo-y-piso").textContent = fmt(s.fixos.y_piso, 0);
    definirConexao("ok", "conectado");
    preencherCarcacas(await obter("/api/carcacas"));
  } catch (e) {
    definirConexao("erro", "sem conexão");
    mostrarVazio(`Erro: ${e.message}`);
  }

  const svg = $("desenho");
  const xy = $("cursor-xy");
  svg.addEventListener("mousemove", (ev) => {
    const r = svg.getBoundingClientRect();
    xy.textContent = `tela ${Math.round(ev.clientX - r.left)}, ${Math.round(ev.clientY - r.top)} px`;
  });
}

document.addEventListener("DOMContentLoaded", iniciar);
