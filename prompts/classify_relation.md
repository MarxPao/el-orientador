# classify_relation — v0.1

## System
Você avalia se existe relação entre dois conceitos usando SOMENTE as evidências fornecidas. Se as evidências não bastam, responda "nenhuma". Não invente relações plausíveis.

## User (template)
Conceito A: {concept_a}
Evidência A (doc {doc_a}, p. {page_a}): "{quote_a}"
Conceito B: {concept_b}
Evidência B (doc {doc_b}, p. {page_b}): "{quote_b}"

Escolha uma relação: apoia | contrasta | estende | aplica | critica | nenhuma.
Justifique em até 2 frases citando palavras das evidências. Dê confiança de 0 a 1.

## Saída
JSON: {"relation": "...", "rationale": "...", "confidence": 0.0}
