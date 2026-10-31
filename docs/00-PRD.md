# PRD — El Orientador (v0.1)

## Problema
Alunos de TCC, mestrado e doutorado enfrentam projetos longos e nebulosos, orientadores com pouco tempo, medo de acusação de fraude com IA e risco de citações inventadas. Chats genéricos não mantêm contexto do projeto, não verificam fontes e não organizam o processo.

## Proposta de valor
Um orientador de IA que conduz o processo (árvore de progresso), constrói com o aluno um mapa de conhecimento verificável da bibliografia dele (editável) e gera um relatório para o orientador humano. Orienta, não escreve pelo aluno.

## Público inicial
Alunos brasileiros de graduação (TCC) e candidatos/alunos de mestrado e doutorado. Interface em pt-BR, ABNT por padrão.

## Escopo do MVP (4 blocos)
1. Fluxo guiado do tema ao pré-projeto (árvore de progresso)
2. Orientador socrático com feedback por rubrica
3. Referências verificadas + mapa de conhecimento com evidência
4. Relatório de progresso para o orientador humano

### Fora do MVP
Simulador de banca por voz, análise estatística, recomendação de periódicos, app mobile nativo, colaboração em tempo real, templates por universidade além de ABNT genérica.

## Histórias de usuário (MVP)
- U1: Como aluno, escolho o tipo de trabalho e vejo uma árvore de progresso com meu próximo passo.
- U2: Como aluno, ao tentar avançar um nó, converso com o orientador, que me questiona e libera ou pede revisão.
- U3: Como aluno, envio PDFs (ou busco por DOI) e recebo um mapa de conceitos com ligações sugeridas.
- U4: Como aluno, clico numa ligação e vejo o trecho do PDF que a sustenta; posso confirmar, editar ou rejeitar.
- U5: Como aluno, vejo lacunas entre temas e as uso para formular meu problema de pesquisa.
- U6: Como aluno, escrevo no editor, com seções ligadas aos nós do mapa e checagem de coerência.
- U7: Como aluno, exporto meu texto em DOCX com ABNT básica e a declaração de uso de IA.
- U8: Como aluno, convido meu orientador, que recebe um relatório de progresso e pode comentar.

## Critérios de aceite do MVP
- 0% de afirmações geradas por IA persistidas sem trecho verificado por código.
- Ligação confirmada/rejeitada persiste e rejeitada não volta a ser sugerida.
- Nenhum bloqueio é intransponível; todo "pular" aparece no relatório ao orientador.
- Relatório inclui: nós concluídos, decisões, ligações confirmadas/rejeitadas, uso de IA e pendências.

## Métricas de produto (hipóteses a validar)
Ativação (aluno cria mapa com >= 5 fontes), retenção semanal durante o semestre, taxa de ligações aceitas, % de usuários que exportam relatório ao orientador, conversão para plano pago.

## Monetização (hipótese)
Plano gratuito limitado; passe por projeto/semestre (faixa de teste R$ 89 a 149) e/ou assinatura mensal (R$ 25 a 50); venda institucional posterior. Validar com alunos antes de fixar preços.

## Riscos principais
Extração de relações pouco confiável; PDFs mal formatados; tolerância de instituições a IA; copyright e privacidade de PDFs; churn pós-defesa.
