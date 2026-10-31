# Arquitetura (proposta)

## Visão geral
```
[Next.js web app] <-HTTPS-> [API (Next.js route handlers / FastAPI)] <-> [PostgreSQL + pgvector]
                                   |                                    [Object storage: PDFs]
                                   +--> [Pipeline worker (Python)] --> [LLMClient] --> provedor de LLM
                                   +--> [Bases bibliográficas: Crossref, OpenAlex, Semantic Scholar, SciELO]
```

## Componentes
- **apps/web:** Next.js + TypeScript + Tailwind. React Flow para árvore e mapa. Tiptap para o editor. Auth por provedor gerenciado.
- **services/pipeline:** Python 3.11 + FastAPI + fila (ex.: Redis/RQ ou fila do Postgres). Ingestão de PDF (PyMuPDF; GROBID opcional para estrutura de artigos; OCR só como fallback), extração, verificação, normalização, ligações, lacunas.
- **Banco:** PostgreSQL com pgvector para embeddings de conceitos e trechos. Esquema em `db/schema.sql`.
- **LLMClient:** interface única (ver `prototype/llm.py`). Provedor e modelo por variável de ambiente. Registrar modelo e versão do prompt em cada chamada.
- **Armazenamento:** PDFs em storage S3-compatível, criptografados em repouso, URLs assinadas.

## Fluxo de ingestão
1. Upload ou DOI -> cria `documents` (metadados vindos das bases, não do LLM).
2. Parser -> `document_pages` com texto por página.
3. Extração (prompt `prompts/extract_claims.md`) -> JSON validado.
4. `verify_quote` por claim -> persiste só os verificados em `claims`.
5. Normalização de conceitos (embeddings + confirmação do usuário em casos duvidosos).
6. Geração de candidatos a ligação (co-ocorrência, citação, similaridade) -> classificação com evidência dos dois lados -> segunda verificação -> `edges` com status `suggested`.
7. Lacunas: pares de temas sem ligação -> busca externa -> `gaps`.

## Fluxo da árvore de progresso
Templates em JSON (`progress_templates`) definem nós, pré-requisitos e critérios de desbloqueio. Cada projeto instancia `progress_nodes`. Desbloqueio = conversa socrática avaliada por rubrica + opção "pular com aviso".

## Segurança e privacidade
Dados do usuário isolados por projeto (RLS no Postgres). Sem treino com dados do usuário. Logs sem conteúdo de documentos. Exclusão de conta apaga PDFs e derivados. Segredos só em variáveis de ambiente.

## Estrutura de pastas alvo
```
apps/web/            # frontend
services/pipeline/   # worker Python (migrar de prototype/)
packages/shared/     # tipos compartilhados (schemas JSON)
db/                  # schema.sql e migrações
prompts/             # prompts versionados
docs/
```
