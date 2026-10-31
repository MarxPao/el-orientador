# Especificação de UX

## Princípios
Sóbrio como um caderno de laboratório. Mapa claro, próximo passo sempre visível. Sem gamificação (XP, medalhas, confete). O aluno nunca fica preso.

## Tokens visuais (manual de marca v2, rascunho; contraste sobre o papel crema)
| Token | Valor | Uso | Contraste |
|---|---|---|---|
| ink | #241E1A | texto principal | 14,25:1 |
| paper | #F6EEDC | fundo | - |
| brand-red | #B3261E | só a marca (logotipo, filete) e texto de erro, sempre com ícone. Nunca em comentário do orientador nem em área grande | 5,66:1 |
| orange | #E8761E | só preenchimento: marca-texto do trecho em trabalho, faixa do logotipo, nó disponível. Nunca texto | 2,58:1 |
| purple (available, gap) | #4B2A7B | voz do orientador: perguntas, comentários, botão principal (um por tela), links, foco, lacuna | 9,49:1 |
| done | #5F6E2F | concluído / ligação confirmada (oliva) | 4,84:1 |
| locked | #6F665D | bloqueado e texto secundário (cinza quente) | 4,87:1 |

Estados: concluído = oliva com ícone; disponível = laranja como preenchimento (texto em ink, 5,52:1); lacuna = roxo pontilhado com ícone e rótulo; bloqueado = cinza quente tracejado; erro = ícone mais texto, nunca só cor.
Tipografia: Alfa Slab One (provisória) no logotipo e títulos curtos; Source Serif 4 no texto longo (18 a 20 px, entrelinha ~1,55); DM Sans na interface. No máximo três famílias. Não depender só de cor: usar também traço (cheio, tracejado, pontilhado) e rótulo.
Tom: se um texto puder ser lido como bronca, reescreva como pergunta. Português do Brasil; "El" é a única palavra em espanhol.
## Telas
1. **Início do projeto:** tipo de trabalho, instituição, norma, prazo, horas semanais.
2. **Árvore de progresso:** colunas por fase (Ideia, Base, Planejar, Método, Análise, Escrita, Defesa). Nós em três estados. Neblina: nós distantes borrados mostrando só o nome. Painel lateral ao selecionar um nó (requisitos, tempo típico, o que libera). Fila de pesquisa (2 a 3 próximos nós) que gera o cronograma.
3. **Nó aberto (gate):** conversa com o orientador sobre a decisão do nó anterior, critérios do desbloqueio, botões "Enviar", "Revisar" e "Pular com aviso".
4. **Biblioteca:** fontes, status de análise (completa / só resumo), alertas (retratado, sem DOI).
5. **Mapa de conhecimento:** grafo de conceitos agrupados por tema. Filtros por status (suggested/confirmed/rejected), por fonte e por tema. Zoom por nível. Ligação confirmada = linha cheia; sugerida = tracejada; lacuna = pontilhada roxa.
6. **Painel de evidência:** ao clicar numa ligação: trecho literal, página, contexto ao redor, botão "Abrir PDF", ações Confirmar / Editar tipo / Rejeitar (com motivo opcional).
7. **Editor:** estrutura em árvore de seções à esquerda (ligadas a nós do mapa), texto ao centro, feedback do orientador à direita. Reordenar na árvore reordena o sumário. Avisos de coerência (seção sem fonte, referência órfã, objetivo sem capítulo).
8. **Relatório ao orientador:** progresso, decisões, ligações, uso de IA, pendências. Exportável em PDF e por link.
9. **Painel do orientador:** leitura e comentários.

## Estados e casos de borda
- Vazio: sem fontes -> convite para enviar PDFs ou buscar por DOI.
- Mudança de problema de pesquisa: nós afetados ganham alerta "revisar", não são apagados.
- Mais de ~30 nós: agrupar em fases/temas, mostrar um nível por vez.
- Mobile: lista vertical de próximos passos; mapa em modo leitura.

## Acessibilidade
Contraste AA, navegação por teclado entre nós, leitor de tela com descrição do estado e das ligações, modo escuro.
