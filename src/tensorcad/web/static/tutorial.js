"use strict";
// tensorcad — tutorial interativo (T8). Só ilustrativo: lê a página e desenha uma camada
// por cima (destaque + legenda). Não chama funções do programa, não envia nada ao
// servidor e não altera dados; a camada bloqueia cliques na página enquanto está aberta.
// O único efeito visível é mostrar a tela de cada etapa (aba Setups ou Layout) e voltar à
// aba original ao sair.

const Tutorial = (() => {
  // aba: "setups" ou "layout"; alvo: seletor (o 1º visível é destacado; etapas sem alvo
  // visível são puladas, ex.: campos de outro layout)
  const ETAPAS = [
    { aba: "layout", alvo: ".abas", titulo: "Duas telas",
      texto: "Setups: monte as transmissões (polias, correia, rpm). Layout: crie os casos, calcule e exporte. Este tutorial só mostra; nada é alterado." },
    { aba: "setups", alvo: "#lista-setups, #tela-setups aside", titulo: "Biblioteca de setups",
      texto: "Setups salvos ficam aqui (neste navegador). Novo, duplicar e excluir. A biblioteca pode ser salva num arquivo .json próprio e aberta em outros projetos." },
    { aba: "setups", alvo: "#form-setup", titulo: "Montar um setup",
      texto: "Nome, polia da máquina (355), polia do motor (125 a 280), comprimento da correia SPB e rpm do motor (WEG 60 Hz). Opcional: banco 2 para calcular R2." },
    { aba: "setups", alvo: "#setup-status", titulo: "Resultado do setup",
      texto: "R_min (0 %), R a 2 % (referência) e R_max (3 %) pela planilha de correias, rpm da máquina e o sufixo do caso (ex.: -170-5000). \"salvar setup\" guarda na biblioteca." },
    { aba: "layout", alvo: ".seletor-layout", titulo: "Opção de layout",
      texto: "Tubo inclinado 45° ou tubo horizontal. Cada layout tem a sua lista de casos; trocar não apaga nada." },
    { aba: "layout", alvo: "[data-campo='cota']", titulo: "Altura H do apoio (45°)",
      texto: "Opcional. Vazia: o programa calcula a faixa admissível e a H recomendada. Preenchida: também verifica essa altura." },
    { aba: "layout", alvo: "[data-campo='altura_tubo']", titulo: "Tubo horizontal",
      texto: "Altura do tubo (opcional; topo do tubo no motor normal, fundo no invertido), comprimento do tubo (curso em x = metade) e o switch de motor invertido." },
    { aba: "layout", alvo: "label[for='banco-duplo']", titulo: "Tensionamento para banco duplo",
      texto: "Liga o segundo centro de arcos O2 (540 mm acima de O1). Cada caso passa a ter R2_min e R2_max; o motor deve ficar a ≥ R1 de O1 e ≤ R2 de O2." },
    { aba: "layout", alvo: "#lista-casos", titulo: "Casos em memória",
      texto: "Todos os casos ficam na memória. Clique num caso para voltar a ele; \"+ novo caso\", duplicar e excluir logo abaixo. O ponto mostra o status." },
    { aba: "layout", alvo: "#lista-setups-layout", titulo: "Casos a partir de setups",
      texto: "\"+ caso\" cria um caso com R e sufixo travados pelo setup (⚙ na lista). Se o setup mudar, o caso avisa e oferece \"atualizar do setup\"." },
    { aba: "layout", alvo: "[data-campo='caso_id']", titulo: "Caso ativo",
      texto: "Nome do caso, carcaça, motor e os raios R_min (0 %) e R_max (3 %). Em casos de setup, só o nome antes do sufixo é editável." },
    { aba: "layout", alvo: "#painel-dimensoes", titulo: "Dimensões (45°)",
      texto: "Medidas padrão da chapa e do motor da carcaça. Altere para simular; o que difere do padrão fica destacado." },
    { aba: "layout", alvo: ".area-desenho", titulo: "Desenho",
      texto: "Roda do mouse aproxima, arrastar move, duplo clique enquadra. Passe o mouse para ver os valores. As caixas no topo ligam e desligam as camadas." },
    { aba: "layout", alvo: "#status", titulo: "Resultado",
      texto: "Status (OK, FORA_RANHURA, FORA_PORCAS, FORA_TENSIONAMENTO, SEM_SOLUCAO, INCOMPATIVEL), faixa admissível, altura recomendada e folga mínima." },
    { aba: "layout", alvo: "#posicoes, #posicoes-th", titulo: "Posições do motor",
      texto: "Posições a 0 % e 3 % na altura recomendada (rec) e na informada (inf). No tubo horizontal: g, x e folgas; com a altura informada, g pode ser ajustado de 1 em 1 mm." },
    { aba: "layout", alvo: ".acoes", titulo: "Salvar e exportar",
      texto: "Salvar e abrir o projeto (.json), exportar a planilha .xlsx (uma aba por caso, com gráficos) e limpar a memória (pede confirmação)." },
  ];

  let raiz = null;
  let destaque = null;
  let legenda = null;
  let visiveis = [];
  let i = 0;
  let abaOriginal = null;

  const visivel = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
  };

  // mostra a tela da etapa (só a visualização: mesmo efeito de clicar na aba)
  function verAba(aba) {
    document.body.dataset.aba = aba;
    for (const b of document.querySelectorAll(".abas button")) b.classList.toggle("ativa", b.dataset.aba === aba);
  }
  function alvoDe(etapa) {
    verAba(etapa.aba);
    return [...document.querySelectorAll(etapa.alvo)].find(visivel) || null;
  }

  function montar() {
    raiz = document.createElement("div");
    raiz.id = "tutorial";
    raiz.setAttribute("role", "dialog");
    raiz.setAttribute("aria-label", "Tutorial");
    destaque = document.createElement("div");
    destaque.className = "tutorial-destaque";
    legenda = document.createElement("div");
    legenda.className = "tutorial-legenda";
    legenda.innerHTML =
      '<p class="tutorial-passo"></p><h3 class="tutorial-titulo"></h3><p class="tutorial-texto"></p>' +
      '<div class="tutorial-botoes"><button type="button" data-t="anterior">anterior</button>' +
      '<button type="button" data-t="proximo" class="principal">próximo</button>' +
      '<button type="button" data-t="sair">sair</button></div>';
    raiz.append(destaque, legenda);
    // a camada absorve cliques e rolagem do mouse: a página não é alterada pelo tutorial
    raiz.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const acao = ev.target.dataset.t;
      if (acao === "anterior") ir(i - 1);
      else if (acao === "proximo") (i >= visiveis.length - 1 ? fechar() : ir(i + 1));
      else if (acao === "sair") fechar();
    });
    raiz.addEventListener("wheel", (ev) => ev.preventDefault(), { passive: false });
    document.body.append(raiz);
  }

  function posicionar(el) {
    el.scrollIntoView({ block: "nearest", inline: "nearest" });
    const r = el.getBoundingClientRect();
    const m = 6;
    Object.assign(destaque.style, {
      left: `${r.left - m}px`,
      top: `${r.top - m}px`,
      width: `${r.width + 2 * m}px`,
      height: `${r.height + 2 * m}px`,
    });
    // legenda abaixo do alvo; se não couber, acima; sempre dentro da janela
    const lw = Math.min(360, window.innerWidth - 24);
    legenda.style.width = `${lw}px`;
    const lh = legenda.offsetHeight || 160;
    let top = r.bottom + m + 10;
    if (top + lh > window.innerHeight - 8) top = Math.max(8, r.top - m - 10 - lh);
    if (top + lh > window.innerHeight - 8) top = Math.max(8, window.innerHeight - lh - 8);
    const left = Math.min(Math.max(8, r.left), window.innerWidth - lw - 12);
    Object.assign(legenda.style, { left: `${left}px`, top: `${top}px` });
  }

  function ir(k) {
    if (k < 0 || k >= visiveis.length) return;
    i = k;
    const etapa = visiveis[i];
    const el = alvoDe(etapa);
    if (!el) return;
    legenda.querySelector(".tutorial-passo").textContent = `${i + 1} de ${visiveis.length}`;
    legenda.querySelector(".tutorial-titulo").textContent = etapa.titulo;
    legenda.querySelector(".tutorial-texto").textContent = etapa.texto;
    legenda.querySelector("[data-t='anterior']").disabled = i === 0;
    legenda.querySelector("[data-t='proximo']").textContent = i === visiveis.length - 1 ? "concluir" : "próximo";
    raiz.dataset.etapa = String(i);
    raiz.dataset.alvo = etapa.alvo;
    posicionar(el);
  }

  function teclas(ev) {
    if (!raiz) return;
    if (ev.key === "Escape") fechar();
    else if (ev.key === "ArrowRight") ir(i + 1);
    else if (ev.key === "ArrowLeft") ir(i - 1);
    else if (raiz.contains(ev.target)) return; // Enter/Tab nos botões do tutorial
    // nenhuma tecla chega à página enquanto o tutorial está aberto
    ev.preventDefault();
    ev.stopPropagation();
  }
  const reposicionar = () => raiz && ir(i);

  function abrir() {
    if (raiz) return;
    abaOriginal = document.body.dataset.aba || "layout";
    // etapas com alvo visível agora (ex.: campos do layout ativo)
    visiveis = ETAPAS.filter((e) => alvoDe(e));
    verAba(abaOriginal);
    if (!visiveis.length) return;
    montar();
    document.addEventListener("keydown", teclas, true);
    window.addEventListener("resize", reposicionar);
    ir(0);
  }

  function fechar() {
    if (!raiz) return;
    raiz.remove();
    raiz = destaque = legenda = null;
    document.removeEventListener("keydown", teclas, true);
    window.removeEventListener("resize", reposicionar);
    verAba(abaOriginal);
  }

  function iniciar() {
    const b = document.getElementById("btn-tutorial");
    if (b) b.addEventListener("click", abrir);
  }

  document.addEventListener("DOMContentLoaded", iniciar);
  return { abrir, fechar, etapas: () => visiveis.map((e) => e.titulo), aberto: () => Boolean(raiz) };
})();
