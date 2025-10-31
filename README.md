# 🧠 Alabia Conductor

Infraestrutura modular para orquestração de LLMs com MCP (Model Context Protocol) em Python.
Suporta chamadas automáticas de função, execução distribuída de ferramentas e integração com RAG.

## 🎯 Caso de Uso Principal

Atendimento inteligente via WhatsApp com:
- ✅ Agendamento automático (Google Calendar)
- ✅ Busca em base de conhecimento (RAG)
- ✅ Respostas contextualizadas (Anthropic Claude)

## 📂 Estrutura

```
alabia-conductor/
├─ apps/
│  └─ orchestrator/          → API FastAPI + MCP Client
│     ├─ main.py
│     ├─ routes/
│     │  └─ chat.py          → POST /chat (WhatsApp integration)
│     ├─ settings.py
│     └─ mcp_client.py
│
├─ packages/
│  ├─ llm/
│  │  └─ anthropic_driver.py → Claude integration
│  │
│  ├─ mcp_servers/
│  │  ├─ calendar_server/    → Google Calendar MCP Server
│  │  ├─ rag_server/         → RAG/File Search MCP Server
│  │  └─ web_search_server/  → Web Search MCP Server
│  │
│  └─ rag/
│     └─ ingest.py           → Indexação de documentos
│
├─ docs/comercial/           → Documentos para RAG
├─ infra/                    → Docker Compose
└─ tests/                    → Testes
```

## 🚀 Quick Start

### 1. Setup

```bash
# Clone
git clone https://github.com/alabia/alabia-conductor.git
cd alabia-conductor

# Virtual env
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Dependências
pip install -r requirements.txt

# Configuração
cp .env.example .env
# Edite .env com suas credenciais
```

### 2. Configurar Google Calendar

```bash
# 1. Criar projeto no Google Cloud Console
# 2. Ativar Calendar API
# 3. Criar credenciais OAuth 2.0
# 4. Baixar JSON e salvar em secrets/google-credentials.json
```

### 3. Indexar Documentos (RAG)

```bash
# Adicione docs em docs/comercial/
python packages/rag/ingest.py
```

### 4. Rodar

```bash
# Desenvolvimento
uvicorn apps.orchestrator.main:app --reload

# Produção (Docker)
docker-compose up -d
```

## 📡 API Endpoints

### POST /chat

Endpoint principal para integração com backend WhatsApp.

**Request:**
```json
{
  "user_id": "5511999999999",
  "message": "Quero agendar uma reunião",
  "context": {
    "name": "João Silva",
    "email": "joao@empresa.com"
  }
}
```

**Response:**
```json
{
  "response": "Ótimo! Temos disponibilidade amanhã às 14h e 16h. Qual prefere?",
  "actions": [
    {
      "tool": "calendar.check_availability",
      "status": "success",
      "result": ["2025-11-01T14:00:00", "2025-11-01T16:00:00"]
    }
  ],
  "needs_followup": true
}
```

## 🛠️ MCP Servers

### Calendar Server
- `create_event(title, datetime, attendees)`
- `check_availability(date_range)`
- `list_events(days=7)`

### RAG Server
- `file_search(query, top_k=5)`
- Base: docs comerciais, FAQ, preços

### Web Search Server (Opcional)
- `search(query, num_results=5)`

## 🔧 Tecnologias

- **LLM**: Anthropic Claude 3.5 Sonnet (MCP nativo)
- **Protocol**: MCP (Model Context Protocol)
- **Framework**: FastAPI + Uvicorn
- **Vector DB**: ChromaDB
- **Embeddings**: OpenAI text-embedding-3-small
- **Deploy**: Docker + Ubuntu AWS

## 📋 Variáveis de Ambiente

Ver `.env.example` para lista completa.

Principais:
```bash
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CALENDAR_CREDENTIALS_JSON=./secrets/google-credentials.json
GOOGLE_CALENDAR_ID=comercial@alabia.com
CHROMA_PERSIST_DIR=./data/chroma_db
```

## 🧪 Testes

```bash
pytest tests/
```

## 📦 Deploy AWS

```bash
# SSH na instância Ubuntu
ssh ubuntu@your-ec2-instance

# Clone e configure
git clone ...
cd alabia-conductor
cp .env.example .env
# Configure .env

# Docker Compose
docker-compose up -d

# Nginx reverse proxy (opcional)
sudo apt install nginx
sudo cp infra/nginx.conf /etc/nginx/sites-available/conductor
```

## 📖 Documentação

- [Setup Google Calendar](./docs/setup-google-calendar.md)
- [Indexação RAG](./docs/rag-indexing.md)
- [Integração WhatsApp](./docs/whatsapp-integration.md)
- [MCP Protocol](https://modelcontextprotocol.io)

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Add nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

Propriedade da Alabia - Uso Interno

## 🆘 Suporte

Dúvidas? Contate o time de desenvolvimento interno.

---

**Alabia** - Transformando atendimento com IA 🚀
