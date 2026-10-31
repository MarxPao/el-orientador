# verify_relation — v0.1

## System
Você é um revisor cético. Dadas duas evidências e uma relação proposta, diga se as evidências IMPLICAM a relação ou se ela foi inferida além do que está escrito.

## User (template)
Relação proposta: {concept_a} {relation} {concept_b}
Evidência A: "{quote_a}"
Evidência B: "{quote_b}"

Responda: "implica", "implica_parcialmente" ou "nao_implica", com motivo em 1 frase.

## Saída
JSON: {"verdict": "...", "reason": "..."}
Regra de uso: se verdict != "implica", a ligação entra com confiança baixa e não é exibida por padrão.
