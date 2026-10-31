# Operações do Beta Fechado (T6.5)

Este documento estabelece o protocolo de execução, métricas e validação de produto para a coorte de **10 a 20 alunos** do Beta Fechado do **El Orientador**.

---

## 1. Perfil da Coorte

- **Tamanho:** 10 a 20 estudantes ativos.
- **Segmentação recomendada:**
  - 50% Graduação em fase de TCC (Ciência da Computação, Engenharia, Educação, Saúde).
  - 30% Alunos ou candidatos a Mestrado (Pré-projeto ou Dissertação em andamento).
  - 20% Doutorandos em fase de revisão bibliográfica ou qualificação.
- **Critério de Inclusão:** Estar ativamente redigindo ou planejando o trabalho com previsão de entrega nos próximos 3 a 12 meses.
- **Orientadores Humanos:** Cada aluno é incentivado a convidar seu orientador real para o portal de leitura e comentários.

---

## 2. Jornada Guiada de 4 Semanas

| Semana | Marco | Ação do Aluno | Critério de Sucesso |
|---|---|---|---|
| **Semana 1** | Onboarding & Delimitação | Cadastro, criação do projeto, diálogo no **Gate Socrático** para delimitar Tema e Problema de Pesquisa. | Passar pelo gate com nota na rubrica $\ge 5/6$ ou registrar justificativa consciente ("Pular com aviso"). |
| **Semana 2** | Bibliografia & Mapa | Upload de 5 a 10 PDFs reais e busca por DOI. Visualização do **Mapa de Conhecimento**. | **Ativação:** $\ge 5$ fontes com claims e evidências literais verificadas. |
| **Semana 3** | Tomada de Decisão & Lacunas | Revisar ligações sugeridas (Confirmar, Editar ou Rejeitar). Explorar nós de **Lacuna** com buscas externas. | $\ge 50\%$ de ligações sugeridas avaliadas; uso da memória de rejeições. |
| **Semana 4** | Escrita & Orientador | Redação das primeiras seções no **Editor Acadêmico**, verificação de coerência, envio do **Relatório ao Orientador** e exportação do DOCX ABNT com **Declaração de IA**. | Exportação de pelo menos 1 versão do manuscrito e emissão do relatório ao orientador. |

---

## 3. Telemetria e Métricas Monitoradas (`GET /beta-metrics`)

O endpoint `/beta-metrics` compila automaticamente os indicadores quantitativos:

```json
{
  "students_registered": 15,
  "projects_total": 15,
  "activation": {
    "threshold_sources": 5,
    "activated_projects": 12,
    "activation_rate": 0.80
  },
  "knowledge_map": {
    "total_edges": 68,
    "total_decisions": 54,
    "confirmed": 38,
    "rejected": 16,
    "acceptance_rate": 0.704,
    "target_acceptance_rate": 0.50
  },
  "socratic_gate": {
    "total_attempts": 32,
    "passed": 26,
    "skipped_with_warning": 6
  },
  "manuscript_and_collaboration": {
    "total_sections": 45,
    "advisor_invites": 8,
    "advisor_comments": 19,
    "advisor_reports_generated": 14
  }
}
```

### Metas Quantitativas do Beta

| Métrica | Meta | Ação se abaixo |
|---|---|---|
| **Taxa de Ativação** ($\ge 5$ fontes) | $\ge 60\%$ | Simplificar fluxo de busca por DOI e upload de PDFs em lote. |
| **Aceitação de Ligações** (confirmadas / decididas) | $\ge 50\%$ | Ajustar prompt `classify_relation.md` e elevar limiar de confiança no second pass. |
| **Precisão de Citações Literais** | $100\%$ determinístico | Nenhuma citação não conferida é salva (Regra Inegociável 1). |
| **Retenção Semanal** (usuários ativos W4 / W1) | $\ge 70\%$ | Identificar gargalos na escrita e aprimorar alertas do cronograma. |

---

## 4. Roteiro de Entrevista Qualitativa e Precificação

Ao final da Semana 4, realizar entrevista de 20 minutos com cada aluno da coorte abordando:

1. **Percepção de Valor:**
   - "Qual módulo gerou o maior alívio mental: a árvore de etapas, o mapa de conceitos com evidências ou a declaração de IA?"
   - "Você sentiu que a IA tentou escrever pelo seu lugar em algum momento?" (Verificar se a regra de não ghostwriting foi mantida com sucesso).
2. **Confiança e Transparência:**
   - "O painel de evidências com a citação literal abriu na página certa? Isso aumentou sua segurança para citar no TCC?"
3. **Reação do Orientador Humano:**
   - "O seu orientador chegou a visualizar o relatório de progresso? O que ele achou das etapas puladas com justificativa?"
4. **Validação de Preço e Modelo de Cobrança:**
   - **Hipótese A (Passe Único por Projeto):** R$ 89 a R$ 149 com acesso até a data da defesa informada no cadastro.
   - **Hipótese B (Assinatura Recorrente):** R$ 29 a R$ 49/mês durante a elaboração do trabalho.
   - *Pergunta de Van Westendorp:*
     - A que preço este serviço pareceria tão caro que você não consideraria comprar?
     - A que preço você consideraria um excelente negócio pelo benefício entregue?
     - A que preço você desconfiaria da seriedade do produto?

---

## 5. Protocolo de Incidentes e Segurança de Dados

1. **Privacidade Absoluta:** PDFs de alunos nunca são enviados para treinamento de modelos de terceiros nem impressos em logs de console (`AGENTS.md`, Regra 6).
2. **Documentos com falha de OCR:** Quando um PDF escaneado for enviado, o sistema sinaliza educadamente que documentos escaneados necessitam de camada OCR legível e sugere ferramentas gratuitas de conversão prévia.
3. **Rastreabilidade Ética:** Qualquer versão submetida à banca ou orientador contém o extrato determinístico de `ai_usage_log`.
