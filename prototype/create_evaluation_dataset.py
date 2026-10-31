"""Generate 10 realistic evaluation PDFs matching docs/06-EVALUATION.md criteria:
- Mixture of PT and EN
- 2-column layouts
- 1 scanned PDF with no selectable text
- 1 long dissertation/thesis (16 pages)
- 7 topical articles in education, knowledge graphs, and AI ethics.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pymupdf

DATA_DIR = Path(__file__).parent / "data" / "pdfs"

def create_two_column_page(doc: pymupdf.Document, title: str, col1_text: str, col2_text: str, page_num: int) -> None:
    page = doc.new_page(width=595, height=842) # A4
    margin = 50
    gap = 20
    col_w = (595 - 2 * margin - gap) / 2
    
    # Header
    page.insert_text(pymupdf.Point(margin, 40), f"{title} — Pág. {page_num}", fontsize=8)
    
    # Column 1
    rect1 = pymupdf.Rect(margin, 60, margin + col_w, 800)
    page.insert_textbox(rect1, col1_text, fontsize=9, align=pymupdf.TEXT_ALIGN_LEFT)
    
    # Column 2
    rect2 = pymupdf.Rect(margin + col_w + gap, 60, 595 - margin, 800)
    page.insert_textbox(rect2, col2_text, fontsize=9, align=pymupdf.TEXT_ALIGN_LEFT)

def create_single_column_page(doc: pymupdf.Document, header: str, body_text: str, page_num: int) -> None:
    page = doc.new_page(width=595, height=842)
    page.insert_text(pymupdf.Point(50, 40), f"{header} — Pág. {page_num}", fontsize=8)
    rect = pymupdf.Rect(50, 70, 545, 800)
    page.insert_textbox(rect, body_text, fontsize=10, align=pymupdf.TEXT_ALIGN_LEFT)

def make_doc01_active_learning(dest: Path):
    doc = pymupdf.open()
    title = "Metodologias Ativas no Ensino Superior"
    p1_c1 = (
        "1. INTRODUÇÃO\n\n"
        "As metodologias ativas de aprendizagem constituem abordagens pedagógicas centradas no estudante, "
        "onde o aluno assume papel protagonista no processo de aquisição do saber acadêmico. "
        "Em contraposição ao ensino tradicional meramente transmissivo, as práticas ativas estimulam a reflexão crítica, "
        "o raciocínio hipotético e o desenvolvimento de habilidades de resolução de problemas complexos.\n\n"
        "Estudos precursores demonstram que a retenção do conhecimento em longo prazo é substancialmente ampliada "
        "quando os estudantes são desafiados a resolver problemas contextualizados em pequenos grupos colaborativos. "
        "A aprendizagem baseada em problemas (ABP) tem se consolidado como um dos métodos mais robustos para alcançar esse intento."
    )
    p1_c2 = (
        "2. REVISÃO TEÓRICA\n\n"
        "A fundamentação epistemológica das metodologias ativas remonta à teoria construtivista de Vygotsky e Piaget. "
        "Conforme salienta a literatura educacional contemporânea, a zona de desenvolvimento proximal (ZDP) "
        "é potencializada pelo diálogo contínuo e pela mediação pedagógica estruturada.\n\n"
        "Entretanto, a simples adoção de dinâmicas ativas em sala de aula sem alinhamento prévio dos objetivos instrucionais "
        "pode gerar sobrecarga cognitiva e desorientação entre os discentes. É imperativo estabelecer critérios claros "
        "de avaliação formativa ao longo de todo o percurso acadêmico."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)

    p2_c1 = (
        "3. METODOLOGIA\n\n"
        "Esta pesquisa investigou três turmas de graduação submetidas ao modelo de sala de aula invertida durante dois semestres. "
        "Os estudantes acessaram videoaulas e leituras preliminares antes dos encontros presenciais síncronos. "
        "Durante as sessões presenciais, os discentes participaram de debates orientados e resolução colaborativa de estudos de caso.\n\n"
        "Os dados foram coletados por meio de questionários validados com escala Likert de 5 pontos e avaliações diagnósticas "
        "aplicadas no início e ao término de cada módulo de estudo."
    )
    p2_c2 = (
        "4. RESULTADOS E DISCUSSÃO\n\n"
        "Os resultados demonstraram um aumento de 32% no desempenho médio dos estudantes nas avaliações formativas "
        "em comparação com as turmas do modelo tradicional expositivo. "
        "Além disso, a taxa de evasão reduziu-se significativamente de 14% para 4% no período analisado.\n\n"
        "Os relatos qualitativos indicaram maior senso de autoeficácia e engajamento discente, "
        "embora uma parcela inicial de alunos tenha relatado resistência à mudança na primeira metade do semestre letivo."
    )
    create_two_column_page(doc, title, p2_c1, p2_c2, 2)

    p3_c1 = (
        "5. O PAPEL DO ORIENTADOR E FEEDBACK\n\n"
        "O papel docente transforma-se de conferencista para facilitador e mentor. "
        "O feedback formativo oportuno e detalhado emergiu como o fator determinante para o sucesso das metodologias ativas. "
        "Sem devolutivas frequentes sobre as lacunas conceituais apresentadas nos trabalhos, os alunos tendem a consolidar "
        "vícios argumentativos e equívocos teóricos que prejudicam a elaboração do trabalho de conclusão de curso (TCC)."
    )
    p3_c2 = (
        "6. CONSIDERAÇÕES FINAIS E REFERÊNCIAS\n\n"
        "Conclui-se que as metodologias ativas promovem maior retenção conceitual e autonomia investigativa no ensino superior, "
        "desde que acompanhadas de suporte tutorial consistente e rubricas avaliativas transparentes.\n\n"
        "REFERÊNCIAS\n"
        "BARROWS, H. S. Problem-based learning in medicine and beyond. San Francisco: Jossey-Bass, 1996.\n"
        "MORAN, J. Metodologias ativas para uma educação inovadora. Porto Alegre: Penso, 2018."
    )
    create_two_column_page(doc, title, p3_c1, p3_c2, 3)

    doc.save(dest)
    doc.close()

def make_doc02_cognitive_load(dest: Path):
    doc = pymupdf.open()
    title = "Cognitive Load Theory in Online Learning Environments"
    p1_c1 = (
        "1. INTRODUCTION\n\n"
        "Cognitive Load Theory (CLT), originally formulated by John Sweller in the late 1980s, provides an empirical framework "
        "for understanding human cognitive architecture and its implications for instructional design. "
        "Working memory is strictly limited in capacity and duration when processing novel information.\n\n"
        "Consequently, instructional systems that overwhelm working memory impede long-term memory schema acquisition "
        "and undermine academic performance. Designing learning interventions requires careful management of mental workload."
    )
    p1_c2 = (
        "2. THREE TYPES OF COGNITIVE LOAD\n\n"
        "CLT distinguishes three types of cognitive load: intrinsic, extraneous, and germane. "
        "Intrinsic cognitive load is determined by the inherent difficulty and element interactivity of the content being studied. "
        "Extraneous cognitive load is generated by suboptimal instructional presentation, poor user interfaces, and redundant guidance.\n\n"
        "Germane cognitive load reflects the working memory resources devoted to schema construction and automation. "
        "Effective educational software must systematically minimize extraneous cognitive load."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)

    p2_c1 = (
        "3. THE SPLIT-ATTENTION AND REDUNDANCY EFFECTS\n\n"
        "The split-attention effect occurs when learners must mentally integrate disparate sources of visual information, "
        "such as separated text and diagrammatic illustrations. "
        "Integrating text directly into graphic representations significantly reduces working memory load.\n\n"
        "Similarly, the redundancy effect demonstrates that presenting identical information simultaneously in spoken "
        "and written form can hinder learning comprehension, because the auditory and visual channels become saturated."
    )
    p2_c2 = (
        "4. EMPIRICAL FINDINGS AND IMPLICATIONS\n\n"
        "In our controlled experiment across 240 graduate students, participants using a split-attention interface "
        "spent 45% more time resolving basic navigational tasks and scored lower on conceptual transfer tests (p < 0.01). "
        "In contrast, participants using integrated evidence side-panels demonstrated superior argument synthesis.\n\n"
        "These findings indicate that academic writing assistants must place primary evidence in close visual proximity "
        "to the synthesis workspace to prevent cognitive disintegration."
    )
    create_two_column_page(doc, title, p2_c1, p2_c2, 2)
    doc.save(dest)
    doc.close()

def make_doc03_scanned(dest: Path):
    # Empty text - simulates scanned document with no OCR
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)
    doc.new_page(width=595, height=842)
    doc.save(dest)
    doc.close()

def make_doc04_thesis(dest: Path):
    # 16-page thesis
    doc = pymupdf.open()
    title = "Dissertação de Mestrado: Grafos de Conhecimento na Orientação Acadêmica"
    
    # Page 1: Cover
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(pymupdf.Point(100, 200), "UNIVERSIDADE EXEMPLO — PROGRAMA DE PÓS-GRADUAÇÃO", fontsize=12)
    p1.insert_text(pymupdf.Point(100, 320), "MODELAGEM DE PROCESSOS DE ORIENTAÇÃO ACADÊMICA", fontsize=14)
    p1.insert_text(pymupdf.Point(100, 345), "BASEADA EM GRAFOS DE CONHECIMENTO E EVIDÊNCIAS", fontsize=14)
    p1.insert_text(pymupdf.Point(100, 450), "Autor: Pesquisador Acadêmico de Exemplo", fontsize=11)
    p1.insert_text(pymupdf.Point(100, 480), "Orientador: Prof. Dr. Orientador Sênior", fontsize=11)
    p1.insert_text(pymupdf.Point(260, 750), "2026", fontsize=11)

    chapters = [
        ("RESUMO", "Este trabalho propõe uma arquitetura baseada em grafos para estruturar a orientação de teses e dissertações. A verificação determinística de citações impede a alucinação de fontes."),
        ("ABSTRACT", "This thesis presents a knowledge graph architecture for academic mentoring. Deterministic citation verification prevents source hallucination in LLM-assisted scientific writing."),
        ("CAPÍTULO 1: INTRODUÇÃO", "A redação científica no ensino superior demanda rigor metodológico e fundamentação bibliográfica sólida. O orientador acadêmico enfrenta elevada carga de orientação individual."),
        ("CAPÍTULO 1.2: PROBLEMA DE PESQUISA", "Como estruturar um ambiente computacional de orientação que preserve a integridade da autoria discente e garanta lastro empírico verificável em cada afirmação teórica?"),
        ("CAPÍTULO 1.3: OBJETIVOS GERAIS E ESPECÍFICOS", "O objetivo geral consiste em desenvolver e validar um modelo de mapa conceitual dinâmico com evidências textuais literais para suporte à escrita acadêmica de pós-graduação."),
        ("CAPÍTULO 2: REFERENCIAL TEÓRICO - PARTE 1", "Grafos de conhecimento fornecem semântica explícita e rastreabilidade ontológica. Cada nó representa um conceito científico unificado, enquanto arestas representam relações tipadas."),
        ("CAPÍTULO 2: REFERENCIAL TEÓRICO - PARTE 2", "A teoria da carga cognitiva indica que a fragmentação documental entre leitor de PDF, notas e editor eleva o esforço mental extraneous do estudante."),
        ("CAPÍTULO 3: ARQUITETURA PROPOSTA", "A arquitetura divide-se em três camadas: ingestão determinística de PDFs, verificação de citações literais por código e grafo interativo de três estados."),
        ("CAPÍTULO 3.2: O GATE SOCRÁTICO", "O gate socrático avalia clareza, justificativa e coerência do problema de pesquisa do estudante sem fornecer respostas prontas nem redigir capítulos inteiros."),
        ("CAPÍTULO 4: EXPERIMENTOS E VALIDAÇÃO", "Realizou-se estudo empírico com vinte pós-graduandos ao longo de doze semanas. Analisou-se a taxa de retenção, precisão de citações e coerência textual."),
        ("CAPÍTULO 4.2: ANÁLISE QUANTITATIVA", "Observou-se conformidade de 100% nas citações verificadas por código determinístico, eliminando completamente referências bibliográficas inexistentes ou incorretas."),
        ("CAPÍTULO 4.3: PERCEPÇÃO DOS ORIENTADORES", "Os orientadores humanos relataram redução de 40% no tempo gasto na checagem mecânica de fontes e maior foco nas discussões conceituais substantivas."),
        ("CAPÍTULO 5: DISCUSSÃO E LIMITAÇÕES", "A principal limitação reside em documentos escaneados de baixa qualidade sem camada de OCR. O modelo depende de texto digital legível."),
        ("CAPÍTULO 6: CONCLUSÃO", "A computação orientada à evidência reforça a integridade acadêmica e apoia o aprendizado autônomo sem substituir o papel insubstituível do orientador humano."),
        ("REFERÊNCIAS BIBLIOGRÁFICAS", "ABNT NBR 6023:2018. Informação e documentação - Referências. Rio de Janeiro: ABNT, 2018.\nSWELLER, J. Cognitive load theory. Psychology of Learning and Motivation, v. 55, 2011.")
    ]

    for idx, (head, text) in enumerate(chapters, start=2):
        body = (
            f"{text}\n\n"
            "Conforme estabelecido pela literatura de metodologia científica, o rigor conceitual exige que cada hipótese "
            "seja fundamentada em evidências sólidas e auditáveis. Durante a elaboração desta dissertação, investigou-se a fundo "
            "o impacto de ferramentas computacionais na prática pedagógica universitária.\n\n"
            "A estruturação dos dados acadêmicos em formato tabular e em grafos permite a rápida identificação de lacunas de pesquisa. "
            "Quando dois conceitos centrais de um tema não possuem conexões empíricas comprovadas na bibliografia levantada, "
            "uma oportunidade de investigação científica se configura de forma transparente."
        )
        create_single_column_page(doc, head, body, idx)

    doc.save(dest)
    doc.close()

def make_doc05_knowledge_graphs(dest: Path):
    doc = pymupdf.open()
    title = "Deterministic Verification in Academic Knowledge Graphs"
    p1_c1 = (
        "1. THE CHALLENGE OF AI HALLUCINATION\n\n"
        "Large language models (LLMs) frequently exhibit catastrophic hallucinations when summarizing academic literature. "
        "In scholarly writing, attributing false findings or non-existent citations to reputable authors constitutes academic misconduct.\n\n"
        "Current retrieval-augmented generation (RAG) architectures reduce errors but do not deterministically guarantee verbatim accuracy. "
        "A semantic match is insufficient when scholarly standards require verbatim grounding."
    )
    p1_c2 = (
        "2. DETERMINISTIC EVIDENCE EXTRACTION\n\n"
        "We propose a strict verification protocol: every claim extracted by an LLM must provide a verbatim quote and page number. "
        "A separate deterministic verification module stringently verifies this quote against the extracted PDF text.\n\n"
        "If a quote is not found character-for-character or via normalized fuzzy boundary matching, "
        "the claim is automatically rejected and never saved to the persistent database."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)

    p2_c1 = (
        "3. THREE-STATE RELATION EDGES\n\n"
        "Extracted edges between concepts follow a three-state lifecycle: suggested, confirmed, and rejected. "
        "Only confirmed edges are eligible to feed the manuscript drafting engine. "
        "Crucially, rejections are permanently recorded by concept pair to prevent redundant suggestions.\n\n"
        "This human-in-the-loop gating preserves user agency and editorial control throughout the investigation."
    )
    p2_c2 = (
        "4. EMPIRICAL BENCHMARK\n\n"
        "Evaluating our system against 50 scientific articles achieved a 94% verification rate on valid extractions. "
        "Zero hallucinated quotations entered the persistent knowledge graph. "
        "Users confirmed 68% of the AI suggested concept relations without modifications."
    )
    create_two_column_page(doc, title, p2_c1, p2_c2, 2)
    doc.save(dest)
    doc.close()

def make_doc06_socratic_tutoring(dest: Path):
    doc = pymupdf.open()
    title = "Socratic Mentoring Dialogue in Graduate Education"
    p1_c1 = (
        "1. INTRODUCTION\n\n"
        "The Socratic method fosters deep learning by asking probing questions rather than directly delivering ready-made answers. "
        "In graduate research, developing a crisp research question is the single most critical milestone for thesis completion.\n\n"
        "Students often present vague topics instead of actionable, delineated problems. "
        "An intelligent tutoring system must challenge the student to define variables, boundaries, and theoretical foundations."
    )
    p1_c2 = (
        "2. RUBRIC-BASED GATE EVALUATION\n\n"
        "We implemented a tripartite rubric assessing: (1) clarity and delimitation, (2) academic justification and societal relevance, "
        "and (3) internal methodological coherence. "
        "Each dimension receives a calibrated score from 0 (insufficient) to 2 (exemplary).\n\n"
        "The gate automatically unlocks downstream tree stages once a threshold of 5 out of 6 points is satisfied."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)

    p2_c1 = (
        "3. CONSCIOUS SKIP WITH AUDIT TRAIL\n\n"
        "To balance pedagogical rigor with learner autonomy, students may consciously skip the Socratic Gate. "
        "However, skipping requires providing an explicit written rationale, which is permanently logged in the advisor audit trail.\n\n"
        "This mechanism prevents student frustration while maintaining academic accountability for the supervising professor."
    )
    p2_c2 = (
        "4. CONCLUSIONS\n\n"
        "Our pilot study with 45 graduate students revealed that students who passed the Socratic gate completed their research proposals "
        "3.4 weeks faster than those following traditional unstructured drafting schedules. "
        "Socratic questioning significantly enhances thesis problem definition."
    )
    create_two_column_page(doc, title, p2_c1, p2_c2, 2)
    doc.save(dest)
    doc.close()

def make_doc07_evidencia_empirica(dest: Path):
    doc = pymupdf.open()
    title = "Evidências Empíricas Sobre Feedback Formativo na Redação Científica"
    p1_c1 = (
        "1. O IMPACTO DO FEEDBACK FORMATIVO\n\n"
        "O feedback formativo na escrita científica difere substancialmente da mera correção gramatical e ortográfica. "
        "Ele incide sobre a coerência do encadeamento lógico entre as premissas teóricas e as conclusões empíricas apresentadas.\n\n"
        "Pesquisas empíricas revelam que comentários orientadores focados na estrutura da argumentação aumentam "
        "a profundidade analítica dos textos acadêmicos em até 40% quando comparados ao feedback apenas avaliativo ou corretivo."
    )
    p1_c2 = (
        "2. ANÁLISE DE LACUNAS E COERÊNCIA\n\n"
        "A detecção de seções sem fonte bibliográfica e objetivos sem capítulo correspondente previne inconsistências estruturais graves. "
        "Ao sinalizar referências órfãs antes da defesa final perante a banca examinadora, "
        "o aluno desenvolve disciplina metodológica e respeito às normas éticas da pesquisa acadêmica.\n\n"
        "A coerência conceitual entre o mapa mental e o texto redigido assegura a organicidade do manuscrito final."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)
    doc.save(dest)
    doc.close()

def make_doc08_spaced_repetition(dest: Path):
    doc = pymupdf.open()
    title = "Spaced Retrieval and Thesis Milestone Scheduling"
    p1_c1 = (
        "1. SPACED RETRIEVAL IN COMPLEX COGNITIVE TASKS\n\n"
        "While spaced repetition is conventionally applied to declarative flashcards, its principles apply directly "
        "to multi-month research projects. Students who revisit and synthesize earlier literature chapters at spaced intervals "
        "demonstrate higher structural cohesion in their final thesis defense.\n\n"
        "Distributing research workload across structured weekly milestones prevents the acute cognitive exhaustion "
        "and procrastination commonly observed in final semester submissions."
    )
    p1_c2 = (
        "2. PACE SCALING AND DEADLINE MONITORING\n\n"
        "Dynamic pacing models adapt projected completion dates according to student self-declared weekly available hours. "
        "When available hours drop below the critical baseline threshold (e.g., 10 hours per week), "
        "the pacing algorithm flags milestone schedule risks proactively.\n\n"
        "Early warning indicators enable advisors to recalibrate research scope before critical thesis deadlines are missed."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)
    doc.save(dest)
    doc.close()

def make_doc09_etica_ia_pos_graduacao(dest: Path):
    doc = pymupdf.open()
    title = "Implicações Éticas e Transparência no Uso de IA na Pós-Graduação"
    p1_c1 = (
        "1. INTEGRIDADE ACADÊMICA E AUTORIA\n\n"
        "A proliferação de modelos geradores de linguagem no meio acadêmico suscita debates urgentes sobre autoria e plágio. "
        "A geração indiscriminada de capítulos completos por inteligência artificial compromete a formação do pesquisador "
        "e viola os preceitos éticos da produção científica original.\n\n"
        "É imperativo estabelecer uma fronteira clara: a inteligência artificial deve orientar, questionar e apontar lacunas, "
        "mas jamais substituir o esforço autoral da redação dissertativa discente."
    )
    p1_c2 = (
        "2. DECLARAÇÃO OBRIGATÓRIA DE USO DE IA\n\n"
        "Normativas internacionais e comitês de ética exigem a declaração explícita de todas as ferramentas de IA utilizadas. "
        "A compilação automática de registros de uso (ai_usage_log) permite gerar anexos auditáveis para cada versão do trabalho. "
        "Esse nível de transparência fortalece a confiança entre discentes, orientadores e bancas examinadoras."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)
    doc.save(dest)
    doc.close()

def make_doc10_systematic_review(dest: Path):
    doc = pymupdf.open()
    title = "Revisão Sistemática da Literatura Sobre Ferramentas de Apoio ao TCC"
    p1_c1 = (
        "1. INTRODUÇÃO E PROTOCOLO PRISMA\n\n"
        "Conduzimos uma revisão sistemática da literatura seguindo rigorosamente as diretrizes metodológicas do protocolo PRISMA. "
        "Buscamos estudos publicados entre 2018 e 2026 nas bases Scopus, Web of Science, SciELO e IEEE Xplore. "
        "Dos 412 artigos identificados inicialmente, 38 preencheram todos os critérios de inclusão após análise cega por pares.\n\n"
        "O objetivo central consistiu em mapear as principais barreiras enfrentadas por estudantes de graduação durante o TCC."
    )
    p1_c2 = (
        "2. PRINCIPAIS ACHADOS E LACUNAS DA LITERATURA\n\n"
        "Os resultados apontaram três dificuldades universais: delimitação do problema de pesquisa (citada em 84% dos estudos), "
        "organização da bibliografia preliminar e manutenção de ritmo constante de escrita acadêmica.\n\n"
        "Notavelmente, menos de 5% das ferramentas digitais disponíveis no mercado ofereciam verificação determinística de citações "
        "ou integração direta com orientadores acadêmicos humanos, evidenciando uma lacuna tecnológica substancial."
    )
    create_two_column_page(doc, title, p1_c1, p1_c2, 1)
    doc.save(dest)
    doc.close()

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Gerando 10 PDFs de avaliação em {DATA_DIR}...")
    
    make_doc01_active_learning(DATA_DIR / "doc01_active_learning_pt.pdf")
    make_doc02_cognitive_load(DATA_DIR / "doc02_cognitive_load_en.pdf")
    make_doc03_scanned(DATA_DIR / "doc03_scanned_archive.pdf")
    make_doc04_thesis(DATA_DIR / "doc04_thesis_academic_advising_pt.pdf")
    make_doc05_knowledge_graphs(DATA_DIR / "doc05_knowledge_graphs_en.pdf")
    make_doc06_socratic_tutoring(DATA_DIR / "doc06_socratic_tutoring_en.pdf")
    make_doc07_evidencia_empirica(DATA_DIR / "doc07_evidencia_empirica_pt.pdf")
    make_doc08_spaced_repetition(DATA_DIR / "doc08_spaced_repetition_en.pdf")
    make_doc09_etica_ia_pos_graduacao(DATA_DIR / "doc09_etica_ia_pos_graduacao_pt.pdf")
    make_doc10_systematic_review(DATA_DIR / "doc10_systematic_review_pt.pdf")
    
    pdfs = list(DATA_DIR.glob("*.pdf"))
    print(f"Sucesso: {len(pdfs)} PDFs gerados:")
    for p in sorted(pdfs):
        print(f" - {p.name} ({p.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
