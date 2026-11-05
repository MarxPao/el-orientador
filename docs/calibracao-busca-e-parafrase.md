# Calibração da busca e da detecção de paráfrase (04/11/2026)

Medido no PC do projeto, com o modelo real `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, lê ~128 tokens por trecho).

## Busca: janela do trecho

30 perguntas sobre um livro de 458 páginas (`fonte_grande.pdf`). Resposta certa = a página onde está a passagem.
Ferramenta: `python -m app.eval_search --pdfs DIR --questions JSON`.

| Janela | Trechos | Método | recall@1 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| ~1000 caracteres (antes) | 1201 | palavras | 0,700 | 0,900 | 0,967 | 0,777 |
| | | significado | 0,400 | 0,600 | 0,633 | 0,488 |
| | | **híbrida (a que o app usa)** | 0,500 | 0,733 | 0,867 | 0,633 |
| ~450 caracteres (agora) | 2804 | palavras | 0,567 | 0,833 | 0,867 | 0,683 |
| | | significado | 0,467 | 0,700 | 0,767 | 0,555 |
| | | **híbrida (a que o app usa)** | **0,667** | **0,867** | **0,933** | **0,756** |

Leitura: com janelas que cabem no que o modelo lê, a busca híbrida passou de 73% para 87% de acerto no top 5 e o MRR de 0,63 para 0,76. A busca só por palavras piorou um pouco (trechos menores diluem o BM25), mas a híbrida compensa.
Os trechos são configuráveis (`CHUNK_TARGET_CHARS`, `CHUNK_MAX_CHARS`, `CHUNK_OVERLAP_CHARS`); com um modelo de contexto longo (e5-large), volte a 1000/1400/150. **Documentos já indexados precisam de "reindexar"** para usar a janela nova.

Limites desta medição: um único livro de literatura, 30 perguntas escritas por mim (uma pergunta = 3,3 pontos). Duas perguntas não foram achadas por nenhum método. Para decidir o modelo, repita com os seus PDFs e perguntas (`scripts/perguntas.exemplo.json`).

Próxima melhoria possível: busca por palavras em trechos grandes (melhor MRR, 0,777) fundida com busca por significado em trechos pequenos.

## Detecção de paráfrase: limite de similaridade

`python scripts/calibrar_parafrase.py` (12 trios escritos à mão: rascunho de IA, reescrita genuína, texto independente do mesmo tema).

| | cosseno | Jaccard |
|---|---|---|
| reescrita vs rascunho | 0,687 a 0,915 (média 0,808) | 0,057 a 0,231 |
| independente vs rascunho | 0,280 a 0,549 (média 0,447) | 0,000 a 0,067 |

O limite antigo (0,88) achava só 17% das reescritas. Novo padrão: **cosseno ≥ 0,62** e **Jaccard ≥ 0,05** (no vão entre os dois grupos, com ~0,07 de folga de cada lado).
Limite desta calibração: os trios são meus, não reescritas reais de alunos, e a amostra é pequena. Acrescente pares seus em `TRIOS` e rode de novo; ajuste com `PARAPHRASE_MIN_SIMILARITY`.
A sugestão continua só uma sugestão: nada conta até o autor confirmar, e agora o export avisa se sobrou sugestão sem resposta.
