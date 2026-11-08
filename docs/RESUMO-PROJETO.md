# El Orientador — Resumo do Projeto

Documento consolidado das ideias discutidas até aqui. Data: 08/11/2026.

---

## 1. A ideia

App para ajudar na escrita de trabalhos acadêmicos: TCC, papers, pré-projeto de mestrado e doutorado, dissertações e teses. O nome "El Orientador" evoca a figura do orientador: ocupado, difícil de alcançar, feedback tardio. A promessa: o orientador que responde às 2h da manhã.

**Pergunta de partida:** por que alguém pagaria por um app se um chat de IA faz o mesmo?

**Resposta:** se o app for só uma interface em volta de um chat, ele não se sustenta. O valor está no que o chat sozinho não entrega.

---

## 2. Onde o chat genérico falha

- **Contexto longo e persistente:** um trabalho tem dezenas de páginas, versões, feedback do orientador e decisões de meses. No chat, tudo se perde ou precisa ser recolado.
- **Fluxo guiado:** muita gente não sabe o que pedir. O app conduz do tema ao problema, aos objetivos, à metodologia e ao cronograma.
- **Referências reais:** IAs inventam citações. Integrar Crossref, Semantic Scholar, OpenAlex, SciELO e Zotero e verificar DOIs reduz o risco.
- **Normas e formatação:** ABNT, APA, Vancouver e modelos de cada instituição, com exportação para Word ou LaTeX.
- **Coerência do trabalho inteiro:** objetivos x metodologia x resultados x conclusão.

**Teste útil:** "O que o usuário faz no meu app que exigiria 20 prompts bem pensados e muita organização manual no chat?"

---

## 3. Posicionamento

- **Orientador, não gerador de texto.** O app questiona, aponta lacunas, cobra prazos e não escreve o capítulo no lugar do aluno.
- **Complemento, não substituto, do orientador humano.** Evita a rejeição de professores e universidades. O aluno chega à reunião com texto melhor e dúvidas mais claras.
- **Integridade acadêmica como dor resolvida.** Registro de como a IA foi usada, declaração de uso e histórico de versões ajudam o aluno que teme ser acusado de fraude.
- **Nome:** "El" dá personalidade, mas mistura espanhol e português e pode confundir buscas e registro de domínio. Testar com alunos se soa como marca ou como erro.

---

## 4. Concorrência e preços

> Os valores vieram de blogs de concorrentes (Paperguide, Tesify) que se colocam em primeiro lugar nos próprios rankings. Confirmar nos sites oficiais antes de usar.

### Internacionais

| Ferramenta | Foco | Preço de entrada (aprox.) |
|---|---|---|
| Paperguide | Busca, revisão de literatura, redação com citações, gerenciador de referências | Grátis; Plus ~US$12/mês (anual); Pro ~US$29; Teams ~US$89 |
| ThesisAI | Rascunho longo gerado de uma vez | ~US$14 a 18/mês (anual) |
| Jenni AI | Autocomplete durante a escrita | Grátis limitado; Plus ~US$12; Pro ~US$29 |
| Paperpal | Revisão de linguagem e pré-submissão | Grátis limitado; Prime ~US$11,58/mês (anual) |
| Thesify | Feedback sobre o rascunho, sem escrever por você | ~US$7 a 17/mês (anual) |

### Brasil

- **Mettzer:** formatação ABNT, sem motor de redação com IA. Preços citados em matéria antiga (R$ 24 mensal, R$ 114 anual), provavelmente desatualizados.
- **Tesify (tesify.pt):** ABNT nativa, antiplágio e referências. Cerca de R$ 39 a 49/mês. Não confundir com o Thesify (thesify.ai).
- **Generalistas:** ChatGPT a R$ 100+ por mês nos comparativos, que é com quem o aluno compara.

### Padrão de ticket

- Pago de entrada: US$7 a 18/mês (cerca de R$ 40 a 100), com desconto anual. Desconto acadêmico em alguns (~30%).
- Tiers altos (US$29 a 89) são para pesquisadores e equipes.
- Quase todos têm plano grátis limitado, que é o concorrente real no preço.
- Sinal para o Brasil: **R$ 25 a 50/mês**.
- O uso se concentra em poucos meses, então a assinatura mensal tem churn alto. Testar **passe por projeto ou semestre** (ex.: R$ 89 a 149) e venda para universidades e cursos de pós.

### Lacuna aparente

Os concorrentes se dividem em escrever, editar/formatar e dar feedback. Nenhum que encontrei acompanha o processo inteiro (cronograma, cobrança, relatório para o orientador humano) com postura socrática e foco em português e ABNT. Isso é uma leitura de pesquisa rápida; pode haver concorrentes não encontrados.

---

## 5. Features do app completo

### Início: do tema ao projeto
- Descoberta de tema por entrevista e teste de viabilidade
- Mapeamento de lacunas na literatura
- Construção guiada do problema, hipóteses, objetivos e justificativa
- Escolha de metodologia com explicação dos porquês
- Verificador de coerência entre problema, objetivos e metodologia
- Pré-projeto no modelo da instituição ou da seleção
- Cronograma realista a partir do prazo e da disponibilidade semanal

### Orientação socrática (o diferencial)
- Modos de orientador (exigente, acolhedor, avaliador de banca)
- Perguntas desafiadoras em vez de respostas prontas
- Simulador de banca e defesa, inclusive por voz
- Detector de argumento fraco, salto lógico e afirmação sem fonte
- Feedback por rubrica por seção
- Diário de pesquisa com memória das decisões

### Revisão de literatura
- Busca em SciELO, CAPES, BDTD, Google Scholar, Crossref, Semantic Scholar, OpenAlex, arXiv
- Verificação de DOI e bloqueio de citação inventada
- Fichamento automático com trecho de origem
- Matriz de síntese, mapa de conceitos e autores
- Importação de Zotero, Mendeley, BibTeX e PDFs; chat com PDFs citando página

### Escrita
- Editor estruturado, IA ciente do documento inteiro
- Ajuda por camadas: estrutura, lacunas, reformulação do que o aluno escreveu. Geração de capítulo completo bloqueada por padrão
- Checagem de consistência global e revisão de clareza e tom acadêmico
- Apoio ao inglês, metas diárias e modo foco

### Dados e análise
- Orientação sobre teste estatístico e interpretação de resultados (SPSS, R, Python, Excel)
- Apoio à análise qualitativa
- Modelos de questionário, roteiro e TCLE, com alerta sobre ética (Plataforma Brasil)

### Normas e formatação
- ABNT (NBR 6023, 10520, 14724), APA, Vancouver e templates por universidade
- Elementos pré-textuais, exportação Word, PDF e LaTeX

### Integridade acadêmica
- Registro automático do uso de IA, declaração pronta, checagem de similaridade
- Histórico de versões que comprova autoria progressiva
- Alerta quando o aluno delega demais

### Colaboração com o orientador humano
- Painel do orientador, relatório automático de progresso, comentários com ajuda para aplicar
- Registro de reuniões; visão agregada para coordenações

### Gestão
- Calendário reverso a partir da defesa, alertas de prazos, lembretes inteligentes, apoio à sobrecarga

### Além do trabalho
- Artigo a partir da dissertação, recomendação de periódicos, slides e resumo para a banca, Lattes, editais e cartas de intenção

### Plataforma
- Mobile e desktop, modo offline no editor, privacidade (textos não treinam modelos), português e acessibilidade

### MVP sugerido (quatro blocos)
1. Fluxo guiado do tema ao pré-projeto
2. Orientador socrático com feedback por rubrica
3. Referências verificadas com ABNT
4. Relatório de progresso para o orientador humano

O resto vira roadmap, ordenado pelo que os primeiros usuários pedirem.

---

## 6. UX: a árvore do conhecimento

Inspiração: árvores tecnológicas de jogos de estratégia (Civilization) e a árvore de passivas de Path of Exile.

### Três camadas, uma mesma linguagem visual
1. **Árvore de progresso:** o que fazer e em que ordem.
2. **Mapa de conhecimento:** o que a literatura diz e como os temas se conectam.
3. **Estrutura do texto:** capítulos e seções que nascem do mapa e permanecem ligados a ele.

### Árvore de progresso
- Estados: concluído, disponível agora, bloqueado. Pré-requisitos ensinam a ordem (metodologia exige objetivos e referencial).
- O desbloqueio é uma conversa socrática curta em que o aluno defende a decisão anterior.
- Ramos paralelos, neblina de guerra (nós distantes borrados), painel ao passar o mouse com requisitos e tempo, fila de pesquisa que vira cronograma, árvores diferentes por tipo de trabalho, ramos laterais opcionais e zoom em níveis.

### Cuidados de UX
1. Não é um jogo: sem XP, medalhas ou confete. Tom sóbrio, de caderno de laboratório.
2. Nunca prender o aluno: permitir pular um nó com aviso, registrado no relatório ao orientador.
3. Pesquisa não é linear: se o problema muda, os nós seguintes ganham "revisar".
4. Evitar árvores com mais de 30 nós: agrupar em fases e mostrar um nível por vez.
5. Mobile: versão vertical ou lista de próximos passos; árvore completa no desktop.

### Mapa de conhecimento editável
Gerado pela IA a partir da bibliografia e editável pelo aluno.

- **Três estados de ligação:** confirmada pelo usuário, sugerida pela IA, rejeitada (lembrada para não sugerir de novo).
- **Toda ligação tem evidência:** clicar abre o trecho do PDF (página e parágrafo).
- **Lacunas** aparecem como nó pontilhado: temas bem representados e sem estudos que os liguem. Isso alimenta o problema de pesquisa.
- **O aluno nomeia as relações** (causa, contraste, extensão, crítica), o que mantém o raciocínio dele.
- **Sincronia com o texto:** nós viram seções do referencial, reordenar a árvore reordena o sumário, e a checagem de coerência aponta seção sem fonte, referência órfã e objetivo sem capítulo.
- **Riscos:** grafo emaranhado (agrupar, filtrar, sugerir 5 por vez), extração errada (mostrar confiança e trecho), mapa tratado como "a verdade" (sugerido deve parecer provisório) e privacidade/direitos de PDFs.
- **Análogos:** Connected Papers, ResearchRabbit e Litmaps (citações entre artigos), Obsidian e Roam (ligação manual de conceitos). O espaço livre aparente é um mapa de conceitos gerado da bibliografia do aluno, editável, com evidência e ligado ao texto. Verificar de perto antes de afirmar que está vazio.

---

## 7. Como a IA processaria os conceitos (e a alucinação)

> Arquitetura proposta, a validar com testes reais. Alucinação não se elimina, se contém.

**Princípio:** a IA lê um conjunto fechado de documentos e só afirma o que consegue apontar nele. Sem trecho, não entra no mapa.

### Pipeline
1. **Ingestão e estrutura:** PDF vira texto estruturado com página e posição. Metadados vêm de bases reais pelo DOI, não do modelo.
2. **Extração com citação obrigatória:** para cada artigo, conceito, afirmação e trecho literal. Um filtro determinístico (código) confere se o trecho existe no texto; se não, descarta.
3. **Qualificar a afirmação:** escopo (população, método, contexto) e grau de certeza ("demonstra" x "sugere").
4. **Normalização de conceitos:** agrupar sinônimos e idiomas por similaridade semântica, ancorar em vocabulários controlados e pedir confirmação nos casos duvidosos.
5. **Proposta de ligações:** candidatos por critérios objetivos (co-ocorrência, citação, proximidade), classificados em poucos tipos (apoia, contrasta, estende, aplica, critica) com evidência dos dois lados e verificação por um segundo modelo ou passada.
6. **Detecção de lacunas:** pares de temas sem ligação, com busca externa por trabalhos que os conectem. Dizer "não encontrei estudos nas buscas feitas", nunca "a lacuna existe".
7. **Revisão humana:** confirmar, editar ou rejeitar; as rejeições melhoram as sugestões futuras.

### Falhas e mitigações

| Falha | Mitigação |
|---|---|
| Trecho real, sentido distorcido | Verificação de implicação por segundo modelo; mostrar contexto |
| Generalização indevida | Campos obrigatórios de escopo e certeza |
| Paper lido só pelo resumo | Rotular e reduzir confiança |
| Artigo retratado ou de baixa qualidade | Checar bases de retratação e avisar |
| Deriva entre idiomas | Normalização com confirmação humana e testes por par de línguas |

### Maturidade
- **Maduro:** parsing de PDF, metadados, busca híbrida, extração estruturada, verificação literal de trecho.
- **Difícil, viável com ressalvas:** normalização de conceitos e classificação de relações.
- **Em aberto:** detecção confiável de lacunas e síntese entre áreas. Tratar como experimental e avisar o usuário.

### Avaliação
Montar um conjunto de referência de 20 a 30 artigos ou teses com conceitos e relações anotados por pesquisadores. Medir: precisão da evidência, taxa de ligações aceitas pelos usuários e taxa de trechos que falham na checagem literal. Isso gera resultado publicável e abre espaço para parceria com uma universidade.

---

## 8. Próximos passos sugeridos

1. **Protótipo de uma semana:** 10 artigos, só as etapas 1 (ingestão), 2 (extração com citação) e 5 (ligações), para testar se a ideia aguenta antes de construir o app.
2. Testar o nome com alguns alunos.
3. Testar Tesify, Thesify e Paperguide na prática e confirmar preços nos sites oficiais.
4. Desenhar a tela de um nó aberto (conversa socrática, critérios de desbloqueio e botão de pular).
5. Definir o modelo de dados (nós, ligações, status, evidência) para levar a um desenvolvedor.
6. Decidir a monetização: assinatura mensal, passe por projeto ou venda para instituições.
