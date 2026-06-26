# Maestri — análise de UI/UX + auditoria do clone

> Data: 2026-06-26 · PT-BR · Fontes: site oficial `themaestri.app` + deep-dive (acchapm1).
> Objetivo: comparar a UI/UX do Maestri com a do maestro console e priorizar melhorias.
> Realidade: Maestri é macOS/SwiftUI/Metal ("Liquid Glass"); não dá pra clonar pixel a
> pixel em GTK4 — a meta é um visual **limpo, escuro e polido**, não idêntico.

## Como é a UI/UX do Maestri
- **Estética:** nativa macOS, **Liquid Glass**, dark mode, minimalista ("everything you
  need, no distractions").
- **Canvas:** infinito, **GPU/Metal**, pan/zoom "buttery smooth"; **semantic zoom** (longe =
  terminais simplificados; perto = TUI pixel-perfect); viewport culling.
- **Terminais:** nós arrastáveis ("drop a new terminal wherever you need"); **attention dot**
  vermelho no cabeçalho.
- **Cabos:** linha **com direção**; **"rope-like cable with physics animation"**; cor por estado.
- **Extras:** sketch à mão; overview 3D dos floors; spotlight/Batuta.
- **Onboarding:** sem conta, baixar e usar.

## Como está o nosso (baseline)
- CSS **mínimo**: `.nodehead { padding }`, `.notehead { #fde68a }`, e `.st-<estado>` pinta o
  **fundo do cabeçalho inteiro** com a cor do estado.
- Cabos = **linhas retas** (cairo), azul p/ usuário; sem curva/física.
- Sem tema escuro do canvas, sem cantos arredondados/borda/sombra nos cards, sem grid.
- Toolbar: −/+/zoom/⚠/tema/conectar/☰ — funcional, plana.
- Atenção = rótulo "⚠ N" + recolore o head todo (não um dot discreto).

## Matriz de gaps (UI/UX) — ✅ ok · 🟡 fraco · ❌ falta
| Aspecto | Maestri | Nosso | Gap |
|---|---|---|---|
| Tema/identidade visual | dark, liquid glass, polido | GTK default + flood de cor | ❌ |
| Cards (cantos/borda/sombra/espaço) | refinados | sem estilo | ❌ |
| Indicador de estado | **dot** discreto | fundo do head inteiro | 🟡 deselegante |
| Cabos | curva tipo corda + cor por estado | reta fina | 🟡 |
| Fundo do canvas | (custom) | liso | 🟡 (faltam grid/profundidade) |
| Zoom | semantic zoom | escala uniforme | ❌ (pesado p/ VTE — adiar) |
| Pan/zoom suavidade | Metal | transform GTK (ok) | ✅ aceitável |
| Toolbar | ferramentas limpas | botões simples | 🟡 |
| Onboarding/empty state | frictionless | nenhum | 🟡 |

## Plano priorizado (valor × esforço em GTK4)
1. **UI-1 — Tema visual (CSS).** 🟢 maior salto percebido, baixo risco. Canvas **escuro**,
   cards com **cantos arredondados + borda sutil + sombra + padding**, cabeçalho com título
   legível; botões/toolbar mais limpos. **Estado vira um DOT** no head (em vez de inundar).
2. **UI-2 — Cabos curvos (bezier) + cor por estado + espessura.** 🟢 cairo `curve_to`; visual
   bem mais "corda". (Física animada = exagero; curva já entrega o efeito.)
3. **UI-3 — Grid de pontos no fundo do canvas.** 🟡 cairo no `do_snapshot` do `_Plane`;
   dá profundidade/sensação espacial.
4. **UI-4 — Toolbar/empty-state.** 🟡 agrupar/ícones; dica quando o canvas está vazio.
5. **Semantic zoom / liquid glass real / overview 3D.** ❌ adiados (pesado/macOS-específico).

> Cada item = 1 PR (PR-por-fase). Começar por **UI-1** (transforma a percepção de qualidade).
