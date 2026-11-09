# Guia de Testes do Piloto Acadêmico (Beta Fechado) — El Orientador

Este documento orienta os participantes do piloto fechado de 10 a 20 estudantes (TCC, Pré-projeto de Mestrado/Doutorado, Dissertação, Tese e Artigos) e seus respectivos orientadores.

---

## 1. O que é o El Orientador

O **El Orientador** é uma aplicação web voltada ao rigor metodológico e à orientação socrática da escrita acadêmica. 

### Diferenciais Fundamentais
1. **A IA orienta, não redige por você:** Ela faz perguntas provocativas, aponta lacunas teóricas e cobra coerência lógica entre problema, objetivos e metodologia. Ela **nunca** gera capítulos inteiros sem intervenção crítica do aluno.
2. **Sem evidência literal, não entra:** Toda afirmação bibliográfica aponta obrigatoriamente para um trecho textual verificado por código determinístico (`quote` literal + página + DOI/ID do documento). Nenhuma citação fantasma é tolerada.
3. **Três estados de ligação:** Toda relação teórica nasce como `suggested` (pela IA); apenas quando você a analisa e marca como `confirmed` ela passa a integrar a base conceitual do seu texto.
4. **Alívio da ansiedade de entrega:** Árvore de progresso com marcos desbloqueáveis e cronograma realista baseado nas suas horas semanais declaradas.
5. **Relatório transparente para o orientador humano:** O orientador recebe um link público seguro com o relatório de progresso, distribuição de proveniência de texto e registro de auditoria de IA.

---

## 2. Roteiro de Teste do Estudante (5 Passos)

### Passo 1: Cadastro e Delimitação do Projeto
1. Acesse o sistema em `http://localhost:3005` (ou no link disponibilizado para o piloto).
2. Na tela de cadastro, insira seu nome acadêmico, e-mail institucional e defina sua senha.
3. Clique em **"Novo projeto"**:
   - Escolha o tipo de trabalho (*TCC, Pré-projeto de Mestrado, Dissertação, etc.*).
   - Defina seu estilo de citação (*ABNT, APA, Vancouver*).
   - Estipule sua data de entrega (deadline) e a disponibilidade semanal de dedicação (em horas).
   - Descreva a formulação preliminar do seu problema de pesquisa.

### Passo 2: Navegação na Árvore de Progresso & Gate Socrático
1. Vá até a aba **"Árvore de progresso"**.
2. Clique no nó inicial disponível (ex.: *Delimitação do Tema* ou *Problema de Pesquisa*).
3. Abra o **Gate Socrático**:
   - Responda às provocações conceituais do orientador virtual.
   - Caso já possua essa etapa validada previamente com seu professor, utilize o **"Pular com aviso consciente"** informando a justificativa. O registro fica gravado para o relatório final.

### Passo 3: Ingestão de Referências Bibliográficas (Mínimo de 5 fontes)
1. Vá até a aba de **Referências / Adicionar Documento**.
2. Para cada um dos seus artigos fundamentais:
   - Insira o **DOI** (ex.: `10.1590/...` ou `10.1016/...`) para buscar metadados de bases oficiais (*Crossref, OpenAlex, Semantic Scholar*).
   - Ou faça o upload do PDF do artigo.
3. Observe a extração de conceitos e a verificação determinística de citações literais com número de página e trecho conferido no documento.

### Passo 4: Curadoria do Mapa de Conhecimento
1. Acesse a aba **"Mapa de conhecimento"**.
2. Visualize os conceitos extraídos da sua bibliografia.
3. Inspecione as ligações sugeridas pela IA:
   - Verifique os trechos literais dos dois artigos que fundamentam a ligação.
   - Tome a decisão crítica: marque como **Confirmada** ou **Rejeitada**.
   - Identifique as *lacunas* (conceitos sem ponte na literatura revisada).

### Passo 5: Redação no Editor e Relatório ao Orientador
1. Acesse o **Editor de Manuscrito**.
2. Estruture as seções conforme o modelo acadêmico adotado.
3. Redija seu texto autoral. Se utilizar auxílio socrático ou síntese dialética de contraponto, verifique o **Prisma de Autoria** que calcula a proveniência exata do texto (humano vs revisão de IA vs citação).
4. Acesse a aba **"Relatório"**:
   - Gere o link seguro de visualização para o seu orientador humano.
   - Exporte o manuscrito em formato Word (.docx) formatado segundo as normas com a Declaração de Uso de IA obrigatória.

---

## 3. Como Enviar seu Feedback

Durante o uso da aplicação, localize no cabeçalho superior direito o botão:
> **"Feedback do Beta"** (ao lado de Sair).

No formulário, avalie:
- Nota geral da experiência (1 a 5).
- Utilidade do diálogo socrático e amadurecimento dos argumentos.
- Grau de confiança na verificação literal de citações (ausência de alucinações).
- Alívio de ansiedade com cronograma e etapas.
- Preferência sobre o modelo de preço e sustentabilidade:
  - **Passe por Projeto (R$ 89 a R$ 149):** Pagamento único com acesso irrestrito até a defesa final.
  - **Assinatura Mensal (R$ 29 a R$ 49/mês):** Pagamento mês a mês apenas durante o período de redação ativa.
- Comentários adicionais e percepção sobre o tom sóbrio e a marca *El Orientador*.

---

## 4. Compromissos de Privacidade e Integridade

- **Seus PDFs não são compartilhados** nem utilizados para alimentar modelos de linguagem externos.
- **Transparência total:** Seu orientador humano recebe exatamente o que você escreveu e como as ferramentas de auxílio foram empregadas, eliminando riscos de acusações de fraude ou plágio.
- **Suporte ao piloto:** Dúvidas técnicas ou dificuldades de conexão podem ser reportadas diretamente à equipe do projeto.
