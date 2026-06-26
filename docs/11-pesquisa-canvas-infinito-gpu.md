# Canvas infinito × GPU do Raspberry Pi — análise e alternativas

> Data: 2026-06-26 · PT-BR · Motivo: a 1ª tentativa de Canvas Infinito (modelo câmera)
> travou a renderização no uConsole CM4 (`MESA: Failed to allocate device memory for BO`).
> Pesquisa em fontes ao vivo p/ entender a causa e achar o caminho certo (foco no CM5).

> ## ⚠️ ATUALIZAÇÃO 2026-06-26 — RESOLVIDO no CM4 (a conclusão "foco no CM5" foi PREMATURA)
>
> O canvas infinito **roda no CM4** (entregue na **v0.24.0**, branch `feat/canvas-infinito`).
> A conclusão original abaixo ("inviável no CM4, adiar pro CM5") estava **errada**, por dois motivos:
>
> 1. **O OOM de GPU não se repete com a GPU limpa.** O `MESA: Failed to allocate ... BO` veio
>    do **1º crash** (plano CSS gigante 5000×4000 — já corrigido p/ plano=viewport). Esse crash
>    **travou o CMA/compositor**, e os testes seguintes herdaram a GPU travada (falsos negativos).
>    Após **reboot**, com o modelo-câmera (plano=viewport), o app roda 5+ min de pan/zoom **sem OOM**.
> 2. **O verdadeiro bloqueador NÃO era GPU** — era um **bug de layout**: a janela inchava/saía da
>    tela ao panar. Causa: `Gtk.Fixed` mede a caixa dos filhos (com a câmera assada no transform) e
>    o `ScrolledWindow` em policy `NEVER` exigia o mínimo inteiro → empurrava o toplevel. **Fix:**
>    policy **`EXTERNAL`** + `Viewport.set_scroll_to_focus(False)`. (Sobrescrever `do_measure` no
>    `Gtk.Fixed` **não** resolve — é ignorado.) Ver **ADR-12** em `architecture.md`.
>
> O que continua válido abaixo: a análise de **CMA/IOMMU** (boa razão para *viewport culling* e nunca
> criar render target gigante — diretrizes seguidas) e o **fallback `GSK_RENDERER`** como rede de
> segurança. O CM5 segue desejável por folga de GPU/RAM ([[hardware-cm5-upgrade]]), mas **não é
> pré-requisito** do canvas infinito.

## Causa-raiz (verificada)
1. **CM4 = Broadcom VideoCore VI (V3D), SEM IOMMU.** Buffers da GPU (texturas, render
   targets) precisam ser **contíguos** → vêm do **CMA** (Contiguous Memory Allocator),
   um pool pequeno/limitado. Buffer grande ou fragmentação → falha de alocação:
   `Failed to allocate from CMA` / `Failed to allocate device memory for BO`. Limitação
   conhecida do Pi4/CM4.
2. **GTK4 renderiza via GSK na GPU** (vulkan/ngl por padrão). Há issues conhecidas de
   apps GTK4 travando no Pi4/CM4 com o renderer padrão; contornadas com `GSK_RENDERER`.
3. **A mudança do canvas infinito empurrou a alocação de GPU além do CMA** do CM4. O app
   da Fase 3 fica abaixo do limite; o caminho de render do infinito passou dele. Reduzir
   o plano (5000×4000 → viewport) ajudou mas não bastou no CM4.

## Por que o CM5 resolve
- **CM5 = VideoCore VII (V3D 7.x), COM IOMMU.** Texturas passam a ser alocadas da **RAM
  geral** (não do CMA) e mapeadas sob demanda → **acaba o gargalo de memória contígua**.
- GPU ~2–3× mais rápida (10+ GFLOPS), OpenGL ES 3.1, Vulkan 1.2.
- Conclusão: o código do infinito (modelo câmera, já pronto e salvo em `git stash`) deve
  rodar liso no CM5.

## Alternativas / mitigações
| Onde | Abordagem |
|---|---|
| **CM5** | Rodar o infinito como está (IOMMU remove o limite). 1ª opção. |
| **Qualquer HW (robustez)** | `GSK_RENDERER=cairo` (software, sem buffer de GPU → sem CMA OOM; mais lento) ou `GSK_RENDERER=gl` (renderer GL antigo, "exige menos da GPU"). Detectar HW fraco e setar o fallback. |
| **Boas práticas de canvas** | *viewport culling* (só desenhar o visível) + *tile-based rendering* + **nunca criar render target gigante** (jeito Figma/mapbox). Manter o plano = viewport. |

## Teste rápido viável no CM4
Recuperar o stash e rodar com `GSK_RENDERER=cairo` (ou `gl`). Se renderizar sem crashar,
o infinito funciona já no CM4 com fallback de renderer — e nativo no CM5.

## Lição de processo
Probe gi-free/headless **não pega OOM de GPU**. Em mudança que afeta o caminho de render
no CM4, testar o **render real** (app na tela) cedo, e ter o fallback `GSK_RENDERER` à mão.

## Fontes (consulta 2026-06-26)
- CMA/VideoCore: [firmware#1247](https://github.com/raspberrypi/firmware/issues/1247) ·
  [vc4 CMA fix](https://forums.raspberrypi.com/viewtopic.php?t=285068) ·
  [Mesa VC4](https://docs.mesa3d.org/drivers/vc4.html)
- CM5/IOMMU/GPU: [CM5 GPU forum](https://forums.raspberrypi.com/viewtopic.php?t=380665) ·
  [Phoronix Pi5 graphics](https://www.phoronix.com/review/raspberry-pi-5-graphics)
- GTK4 renderers: [GTK new renderers](https://blogs.gnome.org/gtk/2024/01/28/new-renderers-for-gtk/) ·
  [GTK running/GSK_RENDERER](https://docs.gtk.org/gtk4/running.html) ·
  [redhat#2282171 (vulkan crash Pi4)](https://bugzilla.redhat.com/show_bug.cgi?id=2282171)
- Infinite canvas: [viewport culling](https://infinitecanvas.cc/example/culling)
