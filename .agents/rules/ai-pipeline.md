# Regras do pipeline de IA (aplicar ao mexer em prototype/ e services/pipeline/)

- Toda saída de LLM é JSON validado por schema (pydantic). Saída inválida = tentar de novo no máximo 2 vezes, depois registrar falha. Nunca "consertar" JSON com regex.
- Fluxo obrigatório: extrair -> verificar trecho literal (código) -> só então persistir.
- Registre em cada claim: `quote_verified` (bool) e `verify_method` (exact | loose | none).
- Afirmações precisam de `scope` (população/método/contexto) e `certainty` (demonstra | sugere | especula | desconhecido).
- Documentos analisados só pelo resumo recebem `analysis_depth = abstract_only` e confiança reduzida.
- Prompts ficam em `prompts/*.md`, versionados, com número de versão no topo. Não escreva prompts inline no código.
- Temperatura baixa (<= 0.2) nas etapas de extração e classificação.
- Limite de sugestões de ligação por sessão: 5. Priorize por confiança e relevância.
