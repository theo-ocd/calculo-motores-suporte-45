"use strict";
// tensorcad — interface web (W0: conexão, dados e lista de carcaças).

const ROTULOS_STATUS = {
  completa: "completa",
  parcial: "parcial",
  a_preencher: "a preencher",
  sem_chapa: "sem chapa",
};

async function obter(caminho) {
  const r = await fetch(caminho, { headers: { Accept: "application/json" } });
  const dados = await r.json();
  if (!r.ok) throw new Error(dados.erro || `HTTP ${r.status}`);
  return dados;
}

function definirConexao(estado, texto) {
  const el = document.getElementById("conexao");
  el.dataset.estado = estado;
  el.textContent = texto;
}

function preencherCarcacas(lista) {
  const ul = document.getElementById("lista-carcacas");
  const sel = document.getElementById("carcaca");
  ul.replaceChildren();
  sel.replaceChildren();
  for (const c of lista) {
    const li = document.createElement("li");
    li.dataset.carcaca = c.carcaca;
    li.title = c.detalhe;
    const nome = document.createElement("span");
    nome.textContent = `${c.carcaca}  (${c.motores.map((m) => m.carcaca).join(", ") || "sem motor"})`;
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.dataset.status = c.status;
    chip.textContent = ROTULOS_STATUS[c.status] || c.status;
    li.append(nome, chip);
    ul.append(li);

    const op = document.createElement("option");
    op.value = c.carcaca;
    op.textContent = `${c.carcaca} — ${ROTULOS_STATUS[c.status] || c.status}`;
    op.disabled = !c.calculavel;
    sel.append(op);
  }
  const primeira = lista.find((c) => c.calculavel);
  sel.disabled = !primeira;
  if (primeira) sel.value = primeira.carcaca;
  mostrarDetalhe(lista);
  sel.onchange = () => mostrarDetalhe(lista);
}

function mostrarDetalhe(lista) {
  const sel = document.getElementById("carcaca");
  const c = lista.find((x) => x.carcaca === sel.value);
  document.getElementById("carcaca-detalhe").textContent = c ? c.detalhe : "";
}

async function iniciar() {
  try {
    const s = await obter("/api/saude");
    document.getElementById("versao").textContent = `v${s.versao}`;
    const fonte = document.getElementById("fonte-dados");
    fonte.textContent = `dados: ${s.dados}`;
    fonte.title = `cadastros: ${s.dados}\nchapas: ${s.padroes}\navisos: ${s.avisos}`;
    definirConexao("ok", "conectado");
    preencherCarcacas(await obter("/api/carcacas"));
  } catch (e) {
    definirConexao("erro", "sem conexão");
    document.getElementById("status").textContent = `Erro: ${e.message}`;
  }

  const svg = document.getElementById("desenho");
  const xy = document.getElementById("cursor-xy");
  svg.addEventListener("mousemove", (ev) => {
    const r = svg.getBoundingClientRect();
    xy.textContent = `tela ${Math.round(ev.clientX - r.left)}, ${Math.round(ev.clientY - r.top)} px`;
  });
}

document.addEventListener("DOMContentLoaded", iniciar);
