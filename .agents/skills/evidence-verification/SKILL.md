---
name: evidence-verification
description: Use ao implementar ou revisar qualquer código que extrai conceitos, afirmações ou relações de PDFs. Garante que cada afirmação tenha trecho literal verificado por código.
---

# Verificação de evidência

1. A extração devolve `quote`, `page` e o `statement`.
2. Chame `verify_quote(quote, pages)` de `prototype/verify_quotes.py`. Aceite `exact` ou `loose`. Rejeite `none` e `too_short`.
3. Persista apenas o que passou. Registre `verify_method`.
4. Nunca peça ao LLM para confirmar que o trecho existe: a checagem é por código.
5. Para relações entre dois conceitos, exija uma evidência verificada de cada lado.
6. Escreva testes com um trecho real, um trecho com hifenização de quebra de linha, um com ligatura e um inventado (deve ser rejeitado).
