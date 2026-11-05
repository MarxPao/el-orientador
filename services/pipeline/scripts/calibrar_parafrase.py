"""Calibra PARAPHRASE_MIN_SIMILARITY com o modelo de embeddings real.

Para cada trio (rascunho de IA, reescrita genuína feita pelo aluno, texto independente sobre o MESMO tema) mede a
similaridade de cosseno e o índice lexical (Jaccard) que app/paraphrase.py usa, e mostra qual limite separa melhor
reescritas de textos apenas parecidos no tema.

  cd services/pipeline
  EMBED_PROVIDER=local python scripts/calibrar_parafrase.py

Amplie TRIOS com textos seus: quanto mais trios, mais confiável o limite.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import embeddings, paraphrase  # noqa: E402

# (rascunho da IA, reescrita genuína do aluno, texto independente sobre o mesmo tema)
TRIOS = [
    ("A aprendizagem significativa ocorre quando o novo conteúdo se conecta de modo substantivo aos conhecimentos que o estudante já possui, de maneira que o aprendiz atribui significado ao que estuda em vez de apenas memorizar.",
     "Quando o aluno consegue ligar o assunto novo ao que já sabe, ele dá sentido ao conteúdo e não se limita a decorar; é isso que caracteriza a aprendizagem significativa.",
     "Os métodos de avaliação da aprendizagem incluem provas, trabalhos em grupo e portfólios, e cada instrumento mede dimensões diferentes do desempenho dos estudantes ao longo do semestre letivo."),
    ("A inflação persistente reduz o poder de compra das famílias e distorce as decisões de investimento das empresas, pois torna os preços relativos menos informativos e eleva a incerteza sobre o retorno futuro dos projetos.",
     "Quando os preços sobem de forma contínua, as famílias compram menos com a mesma renda e as empresas decidem investir com pior informação, já que fica difícil saber o retorno esperado dos projetos.",
     "A inflação brasileira é medida mensalmente pelo IBGE por meio do IPCA, que acompanha uma cesta de bens e serviços consumida por famílias com renda de um a quarenta salários mínimos."),
    ("O capital humano, entendido como o conjunto de conhecimentos e habilidades incorporados aos trabalhadores, eleva a produtividade e contribui para o crescimento econômico de longo prazo dos países.",
     "Os saberes e as competências que as pessoas carregam consigo tornam o trabalho mais produtivo, e por isso o investimento em educação ajuda a explicar por que algumas economias crescem mais no longo prazo.",
     "A migração de trabalhadores qualificados para países ricos, conhecida como fuga de cérebros, preocupa governos de economias emergentes que investiram na formação desses profissionais."),
    ("A credibilidade do banco central é determinante para ancorar as expectativas de inflação, porque agentes que confiam na meta ajustam preços e salários de acordo com ela, tornando a desinflação menos custosa.",
     "Se as pessoas acreditam que o banco central vai cumprir a meta, elas reajustam preços e salários nessa direção, e controlar a inflação custa menos em termos de produto e emprego.",
     "O Comitê de Política Monetária se reúne a cada seis semanas para definir a taxa Selic, e suas atas são divulgadas depois da reunião com a avaliação do cenário econômico."),
    ("A desigualdade de renda tende a persistir entre gerações quando o acesso à educação de qualidade depende da condição econômica da família, o que limita a mobilidade social ascendente dos mais pobres.",
     "Se só as famílias mais ricas conseguem pagar uma boa escola, os filhos dos pobres ficam presos à mesma posição dos pais, e a desigualdade de renda se repete de uma geração para outra.",
     "O coeficiente de Gini varia de zero a um e é a medida mais usada para comparar a concentração de renda entre países, embora não revele em que parte da distribuição ocorrem as diferenças."),
    ("O método de pesquisa qualitativa privilegia a compreensão em profundidade dos significados que os participantes atribuem às suas experiências, utilizando entrevistas e observação em vez de medidas estatísticas.",
     "Em vez de contar e medir, a pesquisa qualitativa procura entender a fundo o que as experiências significam para quem as vive, e para isso recorre sobretudo a entrevistas e à observação.",
     "A amostragem probabilística permite generalizar resultados para a população, desde que cada elemento tenha chance conhecida de ser selecionado e o tamanho da amostra seja suficiente."),
    ("A orientação acadêmica eficaz combina acompanhamento regular com autonomia crescente do estudante, de modo que o orientador faça perguntas que provoquem a reflexão em vez de entregar respostas prontas.",
     "Um bom orientador encontra o aluno com frequência, mas aos poucos o deixa decidir sozinho, fazendo perguntas que o obriguem a pensar em lugar de dar a solução pronta.",
     "O cronograma de um trabalho de conclusão de curso costuma dividir o semestre em etapas de revisão bibliográfica, coleta de dados, análise e redação, com prazos definidos junto ao orientador."),
    ("O comércio internacional gera ganhos quando cada país se especializa nos bens em que possui vantagem comparativa, ainda que um deles seja mais eficiente na produção de todos os bens.",
     "Mesmo que um país produza tudo com mais eficiência que o outro, os dois saem ganhando se cada um se concentrar no que faz com menor custo relativo e depois trocar essas mercadorias.",
     "As barreiras não tarifárias, como cotas de importação e exigências sanitárias, também afetam o fluxo de comércio e muitas vezes pesam mais do que as tarifas sobre os exportadores."),
    ("A carga cognitiva extrínseca decorre da forma como a informação é apresentada e pode ser reduzida eliminando elementos redundantes, o que libera a memória de trabalho para o processamento do conteúdo essencial.",
     "O modo de apresentar a informação pode sobrecarregar a mente sem necessidade; se tirarmos o que é repetido, sobra mais memória de trabalho para o que realmente importa aprender.",
     "A memória de longo prazo armazena esquemas organizados de conhecimento que se formam com a prática repetida e permitem a especialistas reconhecer padrões complexos rapidamente."),
    ("A dívida pública elevada pode restringir a capacidade do governo de responder a choques, pois o pagamento de juros consome recursos que poderiam financiar investimentos e políticas anticíclicas.",
     "Quando o governo deve muito, boa parte da arrecadação vai para os juros e sobra pouco para investir ou reagir a uma crise, o que reduz a sua margem de manobra diante de choques.",
     "A composição da dívida pública brasileira inclui títulos prefixados, indexados à inflação e à taxa Selic, e o Tesouro Nacional publica mensalmente um relatório com o perfil dos vencimentos."),
    ("O plágio acadêmico não se limita à cópia literal; inclui a paráfrase que reproduz a estrutura e as ideias de outro autor sem atribuição, o que exige citação mesmo quando as palavras são diferentes.",
     "Copiar palavra por palavra não é a única forma de plágio: reescrever com outras palavras mantendo as ideias e a organização de outro autor, sem citá-lo, também precisa de referência.",
     "As normas da ABNT definem como apresentar citações diretas curtas, longas e indiretas, além da formatação das referências bibliográficas ao final do trabalho em ordem alfabética."),
    ("A taxa de câmbio flutuante absorve parte dos choques externos, já que a moeda se desvaloriza quando o país perde competitividade, ajudando a restabelecer o equilíbrio do balanço de pagamentos.",
     "Com câmbio flutuante, um choque vindo de fora faz a moeda perder valor, o que devolve competitividade às exportações e ajuda a reequilibrar as contas externas do país.",
     "As reservas internacionais funcionam como seguro contra crises de liquidez, e o Banco Central pode vendê-las no mercado para conter movimentos bruscos e excessivos da cotação do dólar."),
]


def cos(a, b):
    return paraphrase._cosine(a, b)


def main() -> None:
    emb = embeddings.resolve(None)
    if emb is None:
        sys.exit("Nenhum embedder ativo: use EMBED_PROVIDER=local")
    texts = [t for trio in TRIOS for t in trio]
    vecs = emb.embed(texts, task="document")
    pos, neg, jp, jn = [], [], [], []
    for i, (d, p, n) in enumerate(TRIOS):
        vd, vp, vn = vecs[3 * i], vecs[3 * i + 1], vecs[3 * i + 2]
        pos.append(cos(vd, vp)); neg.append(cos(vd, vn))
        jp.append(paraphrase._jaccard(p, d)); jn.append(paraphrase._jaccard(n, d))
    f = lambda xs: f"min {min(xs):.3f}  média {sum(xs) / len(xs):.3f}  max {max(xs):.3f}"  # noqa: E731
    print(f"{len(TRIOS)} trios, modelo {getattr(emb, 'model', '?')}")
    print("cosseno  reescrita vs rascunho  :", f(pos))
    print("cosseno  independente vs rascunho:", f(neg))
    print("jaccard  reescrita              :", f(jp))
    print("jaccard  independente           :", f(jn))
    print(f"limite atual: {paraphrase.min_similarity()}  âncora lexical: {paraphrase.LEXICAL_MIN}\n")
    print("limite  recall(reescritas achadas)  falsos positivos(independentes)")
    best = None
    for t in [x / 100 for x in range(40, 96, 2)]:
        r = sum(1 for p, j in zip(pos, jp) if p >= t and j >= paraphrase.LEXICAL_MIN) / len(pos)
        fp = sum(1 for n, j in zip(neg, jn) if n >= t and j >= paraphrase.LEXICAL_MIN) / len(neg)
        print(f"{t:.2f}    {r:5.2f}                 {fp:5.2f}")
        if fp == 0 and (best is None or r > best[1]):
            best = (t, r)
    if best:
        print(f"\nMenor limite sem falso positivo neste conjunto: {best[0]:.2f} (acha {best[1]:.0%} das reescritas)")
    else:
        print("\nNenhum limite separa os dois grupos sem falso positivo: aumente a âncora lexical ou o conjunto.")


if __name__ == "__main__":
    main()
