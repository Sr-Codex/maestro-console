# Física do cabo do canvas — fluido/orgânico — pesquisa e decisão

> Data: 2026-06-29 · PT-BR · Motivo: deixar o cabo que liga os nós **mais fluido, orgânico e
> com física** (em vez de um bezier estático). Pesquisa ao vivo das abordagens usadas pela
> comunidade (node editors / simulação de corda) antes de implementar.

## Contexto

O cabo era um **cubic bezier estático** entre as pontas (ímã de 8 pontos). Pedido: dar
sensação de cabo **de verdade** — pendurado, com balanço/inércia. Hardware-alvo: **uConsole
CM4 (ARM)**, então custo de CPU/bateria importa.

## Abordagens encontradas (multi-fonte, jun/2026)

1. **Catenária (sag estático)** — curva natural de cabo pendurado sob gravidade; é o que o
   Blender usa para "noodles"/cabos. **Barato** (fórmula fechada / parábola ≈ catenária para
   sags pequenos), dá droop orgânico, mas é **estático** (sem movimento/inércia).
   Fontes: [BlenderNation — Catenary curve](https://www.blendernation.com/2020/03/24/daily-blender-tip-hanging-cables-catenary-curve/),
   [brandon3d — Catenary in Blender](https://brandon3d.com/how-to-add-hanging-catenary-curves-in-blender/).

2. **Verlet rope (física dinâmica)** — corda = cadeia de pontos com **restrições de distância**
   + gravidade, integrada por frame (método de **Thomas Jakobsen, *Advanced Character Physics*,
   GDC 2001**). Dá **sag + balanço + inércia** reais (o cabo chicoteia ao mover o nó). Custa CPU
   por frame enquanto se mexe. Há implementações canvas 2D de referência.
   Fontes: [guerrillacontra/html5-es6-physics-rope](https://github.com/guerrillacontra/html5-es6-physics-rope),
   [toqoz.fyi — Verlet rope in games](https://toqoz.fyi/game-rope.html),
   [jonathanwhiting — Verlet rope](https://jonathanwhiting.com/writing/blog/verlet_rope/).

3. **Bezier + sag + mola** — meio-termo: bezier com uma **caída de gravidade** no ponto de
   controle + uma **mola** que suaviza/atrasa a curva ao mover (catch-up, sem oscilar). Mais
   "vivo" que a catenária, mais barato que o Verlet.

## Decisão

Implementados os **3 modos** (o usuário troca a gosto com **Ctrl+Shift+P**; default **Verlet**),
porque cada um tem uma "sensação" distinta e o custo de manter os 3 é baixo (todos geram uma
lista de pontos desenhada igual). Ver **ADR-14**.

- **Verlet** (padrão): chacoalha e assenta — o mais físico/orgânico.
- **Catenária**: barriga elegante, acompanha calmo, sem balançar — o mais barato.
- **Bezier+mola**: caída leve + atraso suave ao mover — meio-termo; mais **esticado** (menos sag).

**Bateria (uConsole):** a simulação roda num `add_tick_callback` (frame clock GTK4) que **dorme
~0,5 s depois de assentar** — canvas parado = sem tick. As pontas seguem no **ímã de 8 pontos**;
a **troca de âncora** do ímã é suavizada (o endpoint escorrega em vez de teleportar).

## Implementação (resumo)

- Núcleo puro/testável em `maestro/native/rope.py` (`step_rope`/`make_rope` Verlet,
  `catenary_pts`, `spring_target`+`quad_bezier_pts`). Sem GTK → coberto por `tests/test_native_rope.py`.
- Integração e desenho (spline Catmull-Rom, bolinha nas pontas, tracejado de fluxo) em
  `maestro/native/canvas.py` (`_cable_points`/`_step_ropes`/`_cable_tick`).
- Passo de tempo **fixo** (estável p/ Verlet); constantes por-frame a ~60fps.
