# Avaliação do pipeline

## Conjunto de referência
10 artigos para o protótipo (mistura de português e inglês, 2 colunas, 1 com PDF escaneado, 1 tese longa). Depois, 20 a 30 com anotação de pesquisadores ou orientadores.

## Métricas
| Métrica | Como medir | Meta inicial (hipótese) |
|---|---|---|
| Taxa de verificação literal | claims aprovados / claims gerados | >= 85% |
| Precisão da evidência | humano: o trecho sustenta o statement? | >= 90% dos aprovados |
| Escopo/certeza corretos | humano, amostra de 50 claims | >= 80% |
| Ligações aceitas | confirmadas / sugeridas (usuários) | >= 50% |
| Falhas de parsing | PDFs sem texto útil / total | <= 10% |
| Lacunas úteis | humano: faz sentido investigar? | relatar, sem meta |

As metas são hipóteses; ajuste com os primeiros resultados.

## Procedimento
1. Rodar T0.5 e T0.6 nos 10 artigos.
2. Gerar planilha (T0.7); duas pessoas avaliam amostra de 50 claims e 20 ligações.
3. Registrar métricas, exemplos de falha e decisão em `docs/DECISIONS.md`.
4. Mudou prompt ou modelo? Rodar de novo e comparar.
