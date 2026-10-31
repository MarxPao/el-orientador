# Perguntas em aberto e Resoluções

## Resolvidas durante as Sprints 0 a 6
- **Nome do produto:** Mantido como **El Orientador** para o Beta fechado.
- **Provedor e modelo de LLM:** Configurado com Gemini 2.0 Flash por padrão via `LLM_API_KEY` atrás da interface agnóstica `LLMClient` (ver `DECISIONS.md`).
- **Extração de estrutura de PDFs:** Adotado **PyMuPDF puro** (sem servidor externo GROBID), atingindo 95% de verificação literal e 0 falhas em documentos com camada de texto.
- **Autenticação:** Auth próprio em scrypt + JWT HS256 endurecido com suporte simultâneo a cookies `httpOnly` (proteção contra XSS) e `Authorization: Bearer` (APIs e automação), sem custos de fornecedores externos no MVP.
- **Banco de Dados:** Schema relacional com `PostgresRepo` e `db/schema.sql` configurado no `docker-compose.yml` com imagem oficial `pgvector/pgvector:pg16`.
- **Métricas e Telemetria do Beta:** Endpoint `/beta-metrics` implementado e integrado ao repositório para medição em tempo real de ativação, taxa de aceitação de arestas e uso de IA.

## Em validação no Beta Fechado (T6.5)
- **Modelo de Preços:** Validação empírica entre Hipótese A (Passe único por projeto: R$ 89 a R$ 149 até a data da defesa) versus Hipótese B (Assinatura mensal: R$ 29 a R$ 49/mês), conforme roteiro em `docs/07-BETA-OPERATIONS.md`.
- **Sensibilidade a OCR:** Medir porcentagem de alunos que tentam submeter PDFs escaneados antigos e avaliar se haverá necessidade de embutir Tesseract OCR no container da pipeline na versão 1.0.
