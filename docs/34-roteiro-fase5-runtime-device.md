# Roteiro — Fase 5 do review: runtime no device (uConsole CM4)

> **Quem executa:** o usuário (Hydekel), no uConsole CM4 real, X11. O efeito é sensorial —
> nenhum agente pode validar por mim. **Como usar:** rodar `./bin/maestro-canvas` (python do
> SISTEMA, não o venv), seguir cada cenário, marcar ✅/❌ e anotar o que divergiu. Cenários
> marcados 🔗 dobram como verificação de um achado das Fases 2/3 — a coluna "liga com" diz qual.
> Companion do `docs/33-review-producao.md` (Fase 5). Baseline: v0.67.0.

## Como marcar
- ✅ = funcionou exatamente como descrito.
- ⚠ = funcionou mas com ressalva (anotar).
- ❌ = falhou / divergiu (anotar o que viu — vira achado R-Fase5).

---

## Bloco A — Persistência "abre igual fechou" (o coração da regra do projeto)
Para CADA item: muda a config → **fecha o app** → reabre → confere que voltou igual.

| # | Ação | Esperado ao reabrir | Marca | Liga com |
|---|------|--------------------|-------|----------|
| A1 | Pan + zoom pra uma posição/nível | Câmera e zoom idênticos | ☐ | |
| A2 | Move um nó, redimensiona pela borda | Posição e tamanho idênticos | ☐ | |
| A3 | Troca tema/fonte/cor/ícone de um nó (⚙) | Todos idênticos | ☐ | |
| A4 | Cria nota, muda cor/fonte/tamanho, escreve texto | Nota idêntica, texto salvo | ☐ | |
| A5 | Cria grupo, muda cor do grupo, edita brief/objetivo | Grupo/cor/brief idênticos | ☐ | |
| A6 | Cicla física do cabo (Ctrl+Shift+P) pra um modo | Mesmo modo de cabo | ☐ | |
| A7 | Liga toggle de som do monitor num nó | Som segue ligado | ☐ | |
| A8 | Associa uma CONTA a um nó (⚙) | Badge da conta idêntico | ☐ | |
| A9 | Liga "permissão total" num nó | Toggle segue ligado | ☐ | |

## Bloco B — Ciclo de vida do nó (🔗 valida C2/C3 da Fase 2)
| # | Ação | Esperado | Marca | Liga com |
|---|------|----------|-------|----------|
| B1 | Cria nó-agente, deixa rodar, ⏏ Descarregar (confirma) | Vira "descarregado", RAM cai, badge cinza no minimapa | ☐ | |
| B2 | Clica no terminal morto (hint ensina) → retomar | `--resume`, conversa volta com contexto | ☐ | |
| B3 | **Fecha (✕) um nó de conta/permissão total, cria um nó NOVO** | 🔴 O nó novo NÃO herda conta/permissão/role do fechado (nasce limpo) | ☐ | **C2 (herança por id reciclado)** |
| B4 | Com um nó em respawn, aciona **kill-switch/kill-all** | 🔴 Nó NÃO ressuscita depois do kill | ☐ | **C3 (race do kill-switch)** |
| B5 | Simula crash (mata o app com `kill -9`) e reabre | Nó-agente vira órfão âmbar "recuperável"; Reanexar/Novo/Arquivar aparecem | ☐ | |

## Bloco C — Estado/atenção e rotulagem (🔗 valida Fase 6)
| # | Ação | Esperado | Marca | Liga com |
|---|------|----------|-------|----------|
| C1 | Deixa um agente esperando input | Ícone "waiting (é sua vez)" âmbar, distinto de blocked; entra no "⚠ N" | ☐ | |
| C2 | Passa o mouse no ⏏ em cada estado (vivo/descarregado/órfão) | Tooltip diz a verdade em CADA estado (não fixo "libera RAM") | ☐ | **lição ⏏ órfão** |
| C3 | Clica no contador "⚠ N" | Pula pro próximo nó que precisa de você | ☐ | |

## Bloco D — Orquestração e custo
| # | Ação | Esperado | Marca | Liga com |
|---|------|----------|-------|----------|
| D1 | Monta equipe (FAB 🧩) por clique-pra-posicionar | Prévia fantasma segue o cursor; bloco nasce no clique | ☐ | |
| D2 | Liga cabo, faz um agente perguntar a outro (`maestro-ask`) | Resposta volta (headless por padrão) | ☐ | |
| D3 | Seta um budget hard baixo e força gasto | Barra com "pausado por budget" (nunca "falhou"); ▶ retomar aparece | ☐ | |
| D4 | Observa o $ no header de um nó rodando | Custo aparece ao vivo, some quando vazio | ☐ | |

## Bloco E — Paste/drag (🔗 valida C8/C11 da Fase 2, S5 não — S5 é código)
| # | Ação | Esperado | Marca | Liga com |
|---|------|----------|-------|----------|
| E1 | Screenshot pro clipboard, Ctrl+Shift+V num nó | Caminho do PNG injetado SEM Enter (você revisa e envia) | ☐ | |
| E2 | Arrasta um arquivo pro card | Caminho injetado (cópia se sandbox não enxerga) | ☐ | |
| E3 | Ctrl+Shift+V num nó DESCARREGADO | No-op seguro, sem crash | ☐ | **C11 (TOCTOU paste)** |

---

## ⚠ Cenário de segurança que NÃO cabe em teste manual (registro)
O **S1 (spoof de socket, CRÍTICO)** e o **S2 (symlink→escrita no host)** são exploráveis por um
AGENTE, não pelo humano — não há gesto de UI que os reproduza. Ficam para o fix + teste
automatizado de isolamento de box sob bwrap (ver T1 da Fase 4). **Enquanto o S1 não for
corrigido, manter o Maestro mode OFF.** Não tente "testar o S1 no device" manualmente — o
device confirma UX/fluxo, não o modelo de ameaça.

## Onde anotar o resultado
Preencher as marcas aqui e me devolver (colar o que deu ❌/⚠); eu consolido como "Fase 5 —
resultados" no `docs/33` e transformo cada ❌ em achado priorizado.
