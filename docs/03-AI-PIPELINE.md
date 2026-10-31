# Pipeline de IA

Princípio: a IA só afirma o que consegue apontar num trecho literal de documento da bibliografia, e o código confere.

## Etapas
| # | Etapa | Entrada | Saída | Quem decide |
|---|---|---|---|---|
| 1 | Ingestão | PDF/DOI | texto por página + metadados | código + bases reais |
| 2 | Extração | páginas | claims com quote | LLM (`extract_claims.md`) |
| 2b | Verificação | claims | claims verificados | código (`verify_quotes.py`) |
| 3 | Qualificação | claims | scope + certainty | LLM, no mesmo passo da extração |
| 4 | Normalização | conceitos | conceitos canônicos | embeddings + usuário confirma dúvidas |
| 5 | Ligações | pares candidatos | edges suggested | LLM (`classify_relation.md`) + verificação |
| 6 | Lacunas | pares sem ligação | gaps | código + busca externa |
| 7 | Revisão | edges/gaps | confirmed/rejected | usuário |

## Regras
- JSON estrito com schema pydantic (`prototype/schemas.py`).
- Documento lido só pelo resumo: `analysis_depth = abstract_only`, confiança reduzida.
- Artigo retratado: consultar base de retratações e sinalizar.
- Ligação exige evidência verificada nos DOIS lados e passa por segunda verificação (`verify_relation.md`). Divergência = confiança baixa e não exibir por padrão.
- No máximo 5 sugestões novas por sessão.

## Gate socrático (árvore de progresso)
Prompt `socratic_gate.md`: o orientador faz até 3 perguntas sobre a decisão do nó anterior, avalia por rubrica (clareza, justificativa, coerência com nós anteriores) e responde `liberar`, `revisar` com orientação, ou aceita `pular` do usuário. Tudo vai para `gate_attempts` e `ai_usage_log`.

## Limites conhecidos (tratar como experimental)
Normalização entre português e inglês; classificação de relações; detecção de lacunas. A UI deve rotular como "sugerido" e mostrar confiança e evidência.
