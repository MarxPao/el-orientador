# Roadmap

Marque `[x]` ao concluir. Cada tarefa tem critério de aceite. Faça uma por vez.

## Sprint 0 — Protótipo de validação (1 semana)
Objetivo: provar que extração com citação verificada funciona em artigos reais antes de construir o app.

- [x] T0.1 `verify_quotes.py` + testes (hifenização, ligaduras, aspas, trecho inventado). Aceite: `pytest` passa.
- [x] T0.2 `schemas.py` e `pipeline.verify_extraction`. Aceite: filtra claim inventado nos testes.
- [x] T0.3 `prototype/ingest.py`: PDF -> lista de textos por página (PyMuPDF) e salva JSON. Aceite: roda em 10 PDFs de `prototype/data/pdfs/` sem erro; relata PDFs sem texto.
- [x] T0.4 `prototype/llm_client.py`: uma implementação concreta de `LLMClient` (provedor à escolha, chave por env). Aceite: retorna JSON validado; 2 retentativas; erro claro se falhar.
- [x] T0.5 `prototype/extract.py`: roda `prompts/extract_claims.md` por artigo (em blocos de páginas), valida e passa por `verify_extraction`. Aceite: grava `out/<doc>.json` com accepted/rejected e taxa de aprovação.
- [x] T0.6 `prototype/relate.py`: candidatos por co-ocorrência e similaridade, classificação com `classify_relation.md`, exigindo evidência verificada nos dois lados. Aceite: gera `out/edges.json` com no máximo 5 sugestões por rodada.
- [x] T0.7 `prototype/report.py`: métricas (taxa de claims aprovados, % verificados exact vs loose, falhas por PDF) e planilha para avaliação humana. Aceite: CSV com claim, quote, página, campo "correto? (s/n)".
- [x] T0.8 Avaliação com `docs/06-EVALUATION.md` em 10 artigos. Aceite: decisão registrada em `docs/DECISIONS.md` (seguir, ajustar ou pivotar).

## Sprint 1 — Fundação do app
- [x] T1.1 Monorepo, Next.js + Tailwind, FastAPI, Postgres com `db/schema.sql`, auth. Aceite: login e criação de projeto.
- [x] T1.2 Upload de PDF e busca por DOI (Crossref/OpenAlex) com metadados reais. Aceite: documento criado com metadados, sem passar por LLM.
- [x] T1.3 Migrar pipeline do protótipo para `services/pipeline` com fila. Aceite: upload dispara extração e persiste só claims verificados.

## Sprint 2 — Mapa de conhecimento
- [x] T2.1 Tela do mapa (React Flow), três estados de ligação, filtros. Aceite: ligações aparecem com estilos corretos.
- [x] T2.2 Painel de evidência com abertura do PDF na página. Aceite: clique em ligação mostra trecho e abre a página certa.
- [x] T2.3 Confirmar / editar / rejeitar, com memória de rejeições. Aceite: rejeitada não é sugerida de novo.
- [x] T2.4 Lacunas (pares sem ligação + busca externa). Aceite: nó de lacuna com a lista de buscas feitas.

## Sprint 3 — Árvore de progresso e gate socrático
- [x] T3.1 Templates JSON (TCC, pré-projeto de mestrado) e tela da árvore. Aceite: três estados e painel lateral.
- [x] T3.2 Gate socrático (`socratic_gate.md`) com rubrica e "pular com aviso". Aceite: tentativas em `gate_attempts`.
- [x] T3.3 Fila de pesquisa -> cronograma e alertas de prazo.

## Sprint 4 — Editor e coerência
- [x] T4.1 Editor Tiptap com árvore de seções ligada ao mapa.
- [x] T4.2 Checagens de coerência (seção sem fonte, referência órfã, objetivo sem capítulo).
- [x] T4.3 Exportação DOCX com ABNT básica e declaração de uso de IA.

## Sprint 5 — Orientador humano
- [x] T5.1 Convite e painel do orientador.
- [x] T5.2 Relatório de progresso (PDF/link).
- [x] T5.3 Comentários do orientador no documento.

## Sprint 6 — Prontidão e Beta fechado
- [x] T6.1 Empacotamento Docker Compose (FastAPI, Next.js, Postgres 16 com pgvector e schema inicial). Aceite: `docker-compose.yml` e Dockerfiles configurados para subida integrada.
- [x] T6.2 Autenticação endurecida com cookies httpOnly e Bearer tokens (mitigação de XSS). Aceite: testes automatizados de cookie e logout passando.
- [x] T6.3 Healthcheck de produção (`/health`) e documentação de ambiente (`.env.example`). Aceite: resposta 200 com status do app.
- [x] T6.4 Teste de fumaça de ciclo de vida completo do beta (`test_beta_lifecycle.py`). Aceite: 111 testes passando sem falhas.
- [x] T6.5 Testar com 10 a 20 alunos, medir ativação, aceitação de ligações e retenção. Ajustar preço e posicionamento. Aceite: telemetria em /beta-metrics com coorte de 13 alunos, ativação de 76.9% (>=5 fontes), formulário de feedback do piloto (POST/GET /beta/feedback) e calibração de precificação registrada em docs/DECISIONS.md.

## Sprint 7 — Expansão Pós-Beta & Ecossistema Acadêmico
Objetivo: Expandir a interoperabilidade bibliográfica, suporte à oratória acadêmica e formatos institucionais avançados para pós-graduação e publicação.

- [x] T7.1 Busca Direta Integrada em Repositórios Abertos (SciELO, OpenAlex e CAPES/BDTD). Aceite: busca federada por palavras-chave com importação direta de metadados e PDFs abertos sem sair do app.
- [x] T7.2 Simulador Socrático de Defesa de Banca Acadêmica. Aceite: arguição interativa com perfis de examinador (estrito vs construtivo) baseada no manuscrito e matriz de evidências.
- [x] T7.3 Exportação em LaTeX (modelo Overleaf / abnTeX2) e Modelos Institucionais Avançados (capas ABNT, folhas de aprovação, sumário automático). Aceite: download de pacote .zip compilável no Overleaf.
- [x] T7.4 Painel Multi-orientandos para Coordenação de Curso e Professores com turmas. Aceite: visualização agregada de entregas, etapas puladas e alertas de prazo para orientadores com múltiplos estudantes.

