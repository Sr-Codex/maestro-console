# Fluxograma — criar software novo ou feature nova

```mermaid
flowchart TD
    Start(["Preciso criar algo"]) --> Q1{"Software NOVO do zero<br/>ou feature em projeto existente?"}

    Q1 -->|"Novo software"| G1
    Q1 -->|"Feature/melhoria existente"| B1

    subgraph GREEN ["SOFTWARE NOVO (greenfield — BMad completo)"]
        G1["Brainstorm / Brief<br/>problema, público, objetivo"] --> G2["PRD<br/>requisitos e escopo"]
        G2 --> G3["Architecture<br/>stack, decisões, ADR"]
        G3 --> G4["Quebrar em Épicos"]
        G4 --> G5["Escolher próximo Épico"]
        G5 --> G6["Quebrar Épico em Stories"]
        G6 --> G7["Validar Story"]
        G7 --> G8["Dev Story<br/>implementar + testar"]
        G8 --> G9{"Code Review OK?"}
        G9 -->|"Não"| G8
        G9 -->|"Sim"| G10{"Mais stories no épico?"}
        G10 -->|"Sim"| G6
        G10 -->|"Não"| G11["Retrospectiva do Épico<br/>lições + ação"]
        G11 --> G12{"Mais épicos?"}
        G12 -->|"Sim"| G5
        G12 -->|"Não"| G13(["MVP entregue"])
    end

    subgraph BROWN ["FEATURE em projeto existente (dia a dia)"]
        B1["Ideia nova"] --> B2{"É a tarefa de agora?"}
        B2 -->|"Não"| B2b["Registrar no backlog<br/>1 linha"] --> B2c["Continuar tarefa atual"] --> B1
        B2 -->|"Sim"| B3["Analisar estado real"]
        B3 --> B4["Planejar abordagem"]
        B4 --> B5{"Complexo? muitas<br/>partes móveis"}
        B5 -->|"Sim"| B5b["CONFIRMAR com usuário<br/>antes de codar"] --> B6
        B5 -->|"Não"| B6["Pesquisar AO VIVO<br/>fonte + data"]
        B6 --> B7["Validar abordagem"]
        B7 --> B8["Branch curta a partir<br/>da main atualizada"]
        B8 --> B9["Implementar em passos<br/>pequenos + commits granulares"]
        B9 --> B10["Testar 100%<br/>+ sanity-check por reversão"]
        B10 --> B11["Lint limpo +<br/>suite completa"]
        B11 --> B12["CHANGELOG + bump<br/>de versão + docs"]
        B12 --> B13["Push + abrir PR"]
        B13 --> B14{"CI verde?"}
        B14 -->|"Não"| B9
        B14 -->|"Sim"| B15["Usuário testa e<br/>decide o merge"]
        B15 --> B16{"Fim de fase/feature?"}
        B16 -->|"Sim"| B17["Sugerir revisão<br/>do backlog"]
        B16 -->|"Não"| B1
    end

    G13 --> S1
    B15 --> S1

    subgraph SESSION ["FRONTEIRA DE SESSÃO (rodando em paralelo, sempre)"]
        S1["Aprendizado durante<br/>o trabalho (erro/lição)"] --> S2["Capturar em LESSONS.md<br/>/memória NA HORA"]
        S2 --> S3{"Checkpoint natural?<br/>PR fechou · já compactou<br/>1x · troca de tema"}
        S3 -->|"Não, continua"| S1
        S3 -->|"Sim"| S4["Encerrar sessão"]
        S4 --> S5["Sessão NOVA: mini-retro<br/>lê git log/PRs/CHANGELOG<br/>desde o último checkpoint"]
        S5 --> S6["Faltou lição?<br/>completa LESSONS.md/memória"]
        S6 --> Start
    end
```

## Legenda rápida
- **Verde (topo):** só quando é projeto do ZERO — PRD → Architecture → Épicos → Stories, ciclo BMad completo.
- **Azul (meio):** o dia a dia deste e de outros projetos já em andamento — é o fluxo que mais vamos usar.
- **Amarelo (base):** roda o tempo todo, em paralelo — não é uma fase, é a disciplina de não perder aprendizado e de saber quando trocar de sessão.
