# Avaliar a busca com os seus livros

Mede, com números, se a busca acha a página certa: por palavras, por significado e a combinação das duas (a que o app usa). Tudo roda no seu computador.

## 1. Prepare os dados

Crie uma pasta `livros/` com 3 a 5 PDFs seus e um arquivo `livros/perguntas.json` (modelo em `scripts/perguntas.exemplo.json`):

```json
[
  {"pdf": "livro1.pdf", "question": "Como o autor define evasão escolar?", "pages": [34, 35]}
]
```

- 10 a 15 perguntas por livro, escritas como você escreveria ao pesquisar, sem copiar as palavras do trecho. Perguntas que reproduzem o texto só testam a busca por palavras.
- `pages` são as páginas que respondem, contadas como o leitor de PDF mostra (a primeira página é 1), não a numeração impressa do livro.
- Misture perguntas fáceis, com a palavra exata no texto, e difíceis, com sinônimos ou outra formulação.

## 2. Rode

```
docker compose run --rm -v "%cd%\livros:/livros:ro" pipeline python -m app.eval_search --pdfs /livros --questions /livros/perguntas.json --out /tmp/relatorio.json
```

(No PowerShell, troque `%cd%` por `${PWD}`.) A primeira execução com `EMBED_PROVIDER=local` carrega o modelo, o que leva alguns minutos; as seguintes são mais rápidas.

## 3. Leia o resultado

- **recall@5**: fração das perguntas em que uma página certa aparece entre os 5 primeiros resultados. É o número principal.
- **mrr**: quanto mais perto de 1, mais no topo a página certa aparece.
- Se **híbrido** não for melhor ou igual aos outros dois, há algo a ajustar. Se **semântico** ficar muito abaixo de **palavras**, teste o modelo (`LOCAL_EMBED_MODEL`).
- A lista final traz as perguntas que nenhum método achou. Leia-as: às vezes o erro está na pergunta ou na página indicada, às vezes o PDF tem texto ruim (escaneado sem OCR).

Rode de novo depois de trocar de modelo, de ajustar o OCR ou de reindexar, para comparar com o resultado anterior.
