# AGENTS.md — El Orientador

Leia este arquivo inteiro antes de qualquer tarefa. Depois leia `docs/05-ROADMAP.md` para saber a tarefa atual.

## O que é o projeto
App web para orientação acadêmica (TCC, pré-projeto de mestrado/doutorado, artigos). A IA ORIENTA: faz perguntas, aponta lacunas, verifica evidências. Ela NÃO escreve capítulos completos por padrão.
Diferenciais: (1) árvore de progresso estilo árvore tecnológica, (2) mapa de conhecimento gerado da bibliografia do aluno e editável, (3) toda afirmação da IA aponta para um trecho literal verificado, (4) relatório de progresso para o orientador humano.

## Regras inegociáveis
1. **Sem evidência, não entra.** Nenhum conceito, afirmação ou ligação gerada por IA é salvo sem `quote` literal + `page` + `doc_id`. O trecho é conferido por CÓDIGO determinístico (`prototype/verify_quotes.py`), nunca pelo próprio LLM.
2. **Três estados de ligação:** `suggested` (IA), `confirmed` (usuário), `rejected` (usuário). Só `confirmed` alimenta o texto. Rejeições são lembradas para não sugerir de novo.
3. **Metadados bibliográficos vêm de bases reais** (Crossref/OpenAlex/Semantic Scholar via DOI), nunca do LLM.
4. **Lacuna não é afirmação:** escreva "não encontrei estudos nas buscas feitas", nunca "não existem estudos".
5. **Registro de uso de IA:** toda ação de IA grava em `ai_usage_log` (para a declaração de uso e o relatório ao orientador).
6. **Privacidade:** PDFs e textos do usuário nunca vão para logs em texto puro, nem para treino. Não commite PDFs reais.
7. **Não gere capítulo inteiro.** Reformular trecho escrito pelo aluno, apontar lacunas e propor estrutura: ok.
8. **Tom da UI:** sóbrio, de caderno de laboratório. Sem XP, medalhas, confete ou emojis.

## Idioma
- Interface e mensagens ao usuário: português do Brasil, com acentuação correta.
- Código, nomes de variáveis, commits e comentários técnicos: inglês.

## Stack alvo (sugerida, ver docs/01-ARCHITECTURE.md)
Next.js + TypeScript + Tailwind + React Flow (árvore e mapa) + Tiptap (editor) | Python 3.11 + FastAPI (pipeline) | PostgreSQL + pgvector | armazenamento S3-compatível.
Modelo de LLM atrás de uma interface (`LLMClient`), configurado por variável de ambiente. Não acople a um provedor.

## Estrutura do repositório
- `docs/` especificações (PRD, arquitetura, dados, pipeline, UX, roadmap, avaliação)
- `db/schema.sql` esquema do banco
- `prompts/` prompts versionados do pipeline
- `prototype/` Sprint 0: validação do pipeline (extração com citação verificada)
- `.agents/` regras, workflows e skills do Antigravity

## Como trabalhar
1. Em tarefas com mais de um arquivo, use modo Planning e apresente o plano antes de codar.
2. Uma tarefa do roadmap por vez; cada uma tem critérios de aceite. Só marque concluída quando passarem.
3. Todo código novo vem com testes. Rode os testes antes de dizer que terminou.
4. Mudou prompt? Atualize `prompts/` e rode a avaliação (`docs/06-EVALUATION.md`).
5. Dúvida de produto: registre em `docs/OPEN_QUESTIONS.md` e siga com a hipótese mais simples.

## Definição de pronto
Testes passando, sem segredo no código, tipos/linters limpos, critérios de aceite da tarefa atendidos, decisões relevantes anotadas em `docs/DECISIONS.md`.
