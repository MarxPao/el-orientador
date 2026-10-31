# Especificação de UX — Manual de Marca v2

## Princípios
Sóbrio, direto e acolhedor: uma pergunta por vez, e cada afirmação apoiada em um trecho verificado. Mapa claro, próximo passo sempre visível. Sem gamificação (XP, medalhas, confete ou emojis). O aluno nunca fica preso.

## Tokens Visuais (contraste medido sobre o papel crema `#F6EEDC`)

| Token | Variável CSS | Valor | Uso | Contraste sobre o papel |
| :--- | :--- | :--- | :--- | :--- |
| **Papel crema** | `--paper` | `#F6EEDC` | Fundo geral da aplicação | — |
| **Tinta** | `--ink` | `#241E1A` | Texto principal e texto sobre fundo laranja | 14,25:1 |
| **Vermelho** | `--brand-red` | `#B3261E` | Exclusivo da marca: logotipo, filete e carimbo. Nunca em botão, comentário ou área grande | 5,66:1 |
| **Laranja** | `--orange` | `#E8761E` | Só preenchimento: marca-texto do trecho em trabalho/evidência, faixa do logotipo e estado disponível. **Nunca usar como cor de texto** | 2,58:1 (tinta sobre laranja: 5,52:1) |
| **Roxo** | `--purple` | `#4B2A7B` | Voz do orientador e interface: comentários, perguntas, botão principal (um por tela), links, foco e borda de lacuna | 9,49:1 |
| **Oliva** | `--done` | `#5F6E2F` | Estado concluído e ligação confirmada | 4,84:1 |
| **Cinza quente** | `--locked` | `#6F665D` | Estado bloqueado e texto secundário | 4,87:1 |
| **Borda** | `--border` | `#D9CDB4` | Divisórias, contornos de cartões e campos de formulário | — |
| **Superfície** | `--surface` | `#FFFFFF` | Cartões, painéis, área de escrita e respostas do aluno | — |
| **Pulado (fundo)** | `--skipped-bg` | `#EDE7F3` | Fundo roxo claro para etapas puladas com justificativa (texto em `--purple`) | — |

## Estados Padronizados (Árvore, Contadores, Mapa e Relatório)
- **Concluído:** Oliva (`#5F6E2F`), traço cheio, com ícone SVG de verificação e rótulo.
- **Disponível:** Preenchimento laranja (`#E8761E`) com texto em tinta (`#241E1A`), ícone SVG e rótulo.
- **Lacuna (afirmação sem trecho / necessidade de revisão):** Borda roxa (`#4B2A7B`) pontilhada, com ícone SVG e rótulo.
- **Bloqueado:** Cinza quente (`#6F665D`), traço tracejado, com ícone SVG e rótulo.
- **Pulado:** Fundo roxo claro (`#EDE7F3`) com texto roxo (`#4B2A7B`) e rótulo.
- **Erro / Alerta:** Nunca apenas cor; sempre ícone SVG (triângulo ou círculo com `!` em roxo ou tinta) acompanhado de texto claro em tinta. Sem emojis.

## Tipografia (`next/font/google`)
1. **Alfa Slab One (`--font-display`):** Logotipo e títulos curtos de página e de cartão. **Apenas peso 400 (`font-weight: normal`), nunca negrito.** Família isolada em variável CSS para futura substituição por fonte definitiva licenciada.
2. **Source Serif 4 (`--font-serif`):** Textos longos, apoio conceitual e o editor do manuscrito (corpo 18–20 px no manuscrito, entrelinha ~1,55).
3. **DM Sans (`--font-sans`):** Interface (rótulos, botões, tabelas, metadados).
- **Regras:** Nunca mais de três famílias. Corpo mínimo de **15 px** na interface; rótulos curtos em caixa alta podem ter **13 px** com contraste mínimo de 4,5:1.

## Logotipo (`<Logo />` SVG inline)
- `viewBox="0 0 886 190"` (com assinatura) ou `viewBox="0 0 886 135"` (sem assinatura, para larguras abaixo de 160 px e para o cabeçalho).
- `"EL"` em `x=0, y=100, font-size=100, textLength=130`; `"ORIENTADOR"` em `x=166, y=100, font-size=100, textLength=720, lengthAdjust="spacingAndGlyphs"`.
- Faixa laranja em `y=116` (`height=6, width=886`) e filete em `y=127` (`height=2.5, width=886`).
- Assinatura `"PESQUISA · CIÊNCIA · ESCRITA"` em DM Sans 700, `font-size=24`, `letter-spacing=9`, `text-anchor="middle"`, `x=443, y=172`.
- **Variantes:** `padrao` (sobre papel), `invertida` (texto e filete em papel, faixa laranja, sobre fundo roxo), `uma-cor` (tudo roxo) e `withSignature={false}`.

## Componentes e Layout
- **Cabeçalho fixo (68 px):** Nas telas internas, logotipo sem assinatura (~190 px) à esquerda, navegação por abas do projeto e botão "Sair" à direita.
- **Largura útil:** 1200 a 1440 px, alinhada à esquerda, estruturada em colunas e cartões sobre fundo papel crema.
- **Botão principal:** Roxo (`#4B2A7B`), texto papel (`#F6EEDC`), 52 px de altura, raio de 10 px. **Apenas UM botão principal por tela.**
- **Botão secundário:** Contorno roxo (`#4B2A7B`), fundo superfície ou papel.
- **Fala do orientador:** Balão roxo (`#4B2A7B`) com texto papel (`#F6EEDC`) e raio de 12 px. Respostas e comentários do aluno ficam em cartão branco (`#FFFFFF`).
- **Acessibilidade:** Contraste AA/AAA, foco visível (`2px solid #4B2A7B`), área mínima de toque de 44 px.

## Telas
1. **Entrar e Criar conta (`/entrar`):** Tela dividida. Painel esquerdo roxo (~480 px) com logotipo invertido, título `"Uma pergunta por vez."`, linha de apoio em Source Serif 4 e exemplo ilustrativo (frase com marca-texto laranja, balão roxo de pergunta e carimbo de atenção). Painel direito crema com formulário de 400 px. Botão principal: `"Entrar"` / `"Criar conta"`.
2. **Projetos (`/projetos`):** Coluna principal com cartões de projetos (título em Alfa Slab One, metadados, barra de progresso em oliva, próxima etapa com marca-texto laranja e atalhos em roxo) + coluna lateral de 400 px com formulário `"Novo projeto"`. Botão principal: `"Criar projeto"`.
3. **Árvore de progresso (`/projetos/[id]/arvore`):** Colunas por fase, contador superior com as cores exatas de estado (disponível em laranja com texto tinta), painel de cronograma e painel lateral de detalhes da etapa. Botão principal: `"Responder ao orientador"`.
4. **Gate Socrático (Modal):** Conversa com balões roxos para as perguntas do orientador e cartões brancos para o aluno. Botão principal: `"Responder"`.
5. **Mapa de conhecimento (`/projetos/[id]/mapa`):** Grafo de conceitos e painel de evidência literal com trecho em marca-texto laranja. Botão principal: `"Confirmar ligação"` (quando inspecionando sugestão) ou `"Enviar PDF"`.
6. **Editor (`/projetos/[id]/editor`):** Árvore de seções à esquerda, manuscrito em Source Serif 4 ao centro e painel lateral com abas Coerência (rótulos traduzidos com acentuação correta), Conceitos e Comentários (balões roxos do orientador). Botão principal: `"Exportar DOCX (ABNT)"`.
7. **Relatório ao orientador (`/projetos/[id]/relatorio`):** Progresso, etapas puladas com justificativa, lacunas identificadas pelo nome dos conceitos (`Conceito A ↔ Conceito B`) e log auditável de IA. Botão principal: `"Imprimir / Salvar PDF"` (e `"Atualizar relatório"` como secundário).
