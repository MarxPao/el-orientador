# Rodar no Windows sem Docker

Requisitos: Python 3.12 ou 3.13 e Node 20+. Dê duplo clique em `iniciar.bat`.
- Banco: Postgres embutido (pacote `pixeltable-pgserver`), dados em `data/pg`; PDFs em `data/storage`.
- Primeira execução instala tudo (demora); depois abre em segundos. Site: http://localhost:3000.
- Chave de IA (opcional): defina `LLM_PROVIDER`, `LLM_MODEL` e a chave antes de iniciar.
- OCR de PDFs escaneados exige o Tesseract instalado (opcional; sem ele PDFs com texto funcionam normalmente).
