# Modelo de dados

Esquema SQL completo em `db/schema.sql`. Resumo dos conceitos:

- **projects:** trabalho do aluno (tipo, instituição, norma, prazo).
- **documents / document_pages:** fontes bibliográficas e texto por página.
- **claims:** afirmações extraídas, SEMPRE com `quote`, `page_no`, offsets e `quote_verified`.
- **concepts:** nós do mapa (rótulos pt/en, aliases, embedding).
- **edges:** ligações entre conceitos com `relation_type`, `status` (suggested | confirmed | rejected), `confidence`, `created_by`.
- **edge_evidence:** liga cada edge a claims (um de cada lado).
- **gaps:** lacunas detectadas (par de conceitos, buscas feitas, resultado).
- **sections:** estrutura do texto (árvore), ligada a conceitos.
- **progress_templates / progress_nodes:** árvore de progresso.
- **gate_attempts:** conversas socráticas de desbloqueio e resultado.
- **ai_usage_log:** registro de toda ação de IA.
- **advisor_reports / advisor_members:** relatório e acesso do orientador humano.

## Regras de integridade
- `claims.quote_verified` precisa ser true para existir referência em `edge_evidence` de edge `suggested`/`confirmed`.
- `edges` rejeitadas ficam guardadas (nunca apagar) para impedir nova sugestão.
- Exclusão de projeto remove em cascata documentos, claims, edges e arquivos.
