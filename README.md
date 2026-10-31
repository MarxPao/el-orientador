# El Orientador

App de orientação acadêmica com IA: árvore de progresso, mapa de conhecimento verificável da bibliografia e relatório para o orientador humano.

## Conteúdo do pacote
```
AGENTS.md                       instruções do projeto para o agente (Antigravity lê automaticamente)
.agents/rules/                  regras por tema (pipeline de IA, UX)
.agents/workflows/start-sprint.md   comando /start-sprint
.agents/skills/evidence-verification/   skill de verificação de evidência
docs/                           PRD, arquitetura, dados, pipeline, UX, roadmap, avaliação
db/schema.sql                   esquema PostgreSQL + pgvector
prompts/                        prompts versionados do pipeline
prototype/                      Sprint 0: verificador de trechos + schemas + testes (9 testes passando)
```

## Como começar no Antigravity
1. Descompacte e abra a pasta `el-orientador` como workspace.
2. Confira em Customizations > Rules que o `AGENTS.md` e as regras de `.agents/rules/` aparecem. Rodar `/start-sprint` deve listar a tarefa T0.3.
   (A leitura de `AGENTS.md` e a pasta `.agents/` seguem a documentação e guias do Antigravity pesquisados em 29/10/2026; a interface muda entre versões, então confirme na sua.)
3. Teste o que já funciona:
   ```
   cd prototype && pip install -r requirements.txt && python -m pytest -q
   ```
4. Use o modo Planning e cole este primeiro prompt:

> Leia AGENTS.md, docs/00-PRD.md, docs/03-AI-PIPELINE.md e docs/05-ROADMAP.md. Execute a tarefa T0.3 (ingest.py) do Sprint 0. Antes de codar, mostre o plano. Depois implemente, escreva testes e rode `pytest`. Não avance para outra tarefa.

5. Coloque 10 PDFs de artigos reais em `prototype/data/pdfs/` (não commite). Siga o roadmap em ordem: T0.3 a T0.8.
6. Ao fim do Sprint 0, registre a decisão (seguir, ajustar ou pivotar) em `docs/DECISIONS.md` antes de construir o app.

## Observações
- Arquivos de regras do Antigravity têm limite de ~12.000 caracteres cada (segundo um guia de terceiros); os daqui ficam bem abaixo.
- Escolha de provedor e modelo de LLM, GROBID e preços ficam em aberto (`docs/OPEN_QUESTIONS.md`).
- Os números de metas e preços são hipóteses para validar, não fatos.
