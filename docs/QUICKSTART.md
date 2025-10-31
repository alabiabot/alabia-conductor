# 🚀 Quick Start - Alabia Conductor

Guia rápido para rodar o projeto em **desenvolvimento** ou **produção**.

---

## 📋 Pré-requisitos

- Python 3.11+
- Docker e Docker Compose (para produção)
- Credenciais:
  - Anthropic API Key
  - OpenAI API Key (para embeddings)
  - Google Calendar credentials (opcional)

---

## 🏃 Desenvolvimento Local

### 1. Clone e Setup

```bash
# Clone
git clone https://github.com/alabiabot/llm-tools-orchestrator.git
cd llm-tools-orchestrator

# Virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt
```

### 2. Configurar .env

```bash
# Copiar template
cp .env.example .env

# Editar com suas credenciais
nano .env
```

**Mínimo necessário:**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...
```

### 3. Indexar Documentos (RAG)

```bash
# Indexar docs comerciais
python packages/rag/ingest.py docs/comercial/

# Verificar indexação
python -c "
from packages.rag.ingest import DocumentIngester
ing = DocumentIngester()
print(ing.collection.count(), 'documentos indexados')
"
```

### 4. Rodar API

```bash
# Modo development (com reload)
uvicorn apps.orchestrator.main:app --reload

# Acessar:
# - http://localhost:8000
# - http://localhost:8000/docs (Swagger UI)
```

### 5. Testar Endpoint

```bash
# Health check
curl http://localhost:8000/health

# Chat test
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5511999999999",
    "message": "Quanto custa o plano professional?",
    "context": {
      "name": "Teste"
    }
  }'
```

---

## 🐳 Produção (Docker)

### 1. Setup

```bash
# Clone e configure
git clone https://github.com/alabiabot/llm-tools-orchestrator.git
cd llm-tools-orchestrator

# Configure .env
cp .env.example .env
nano .env

# Adicione suas credenciais e ajuste para produção:
ENVIRONMENT=production
DEBUG=false
API_RELOAD=false
```

### 2. Deploy

```bash
# Deploy automático
./infra/deploy.sh

# Ou manual:
cd infra
docker-compose up -d

# Verificar logs
docker-compose logs -f orchestrator
```

### 3. Indexar Documentos

```bash
# Via container
docker-compose exec orchestrator python packages/rag/ingest.py docs/comercial/

# Ou local se tiver Python
python packages/rag/ingest.py docs/comercial/
```

### 4. Verificar

```bash
# Status dos containers
docker-compose ps

# Health check
curl http://localhost:8000/health

# Logs
docker-compose logs -f
```

---

## 🔧 Configurar Google Calendar (Opcional)

### 1. Google Cloud Console

1. Acesse https://console.cloud.google.com
2. Crie projeto ou use existente
3. Ative **Google Calendar API**
4. Crie credenciais OAuth 2.0:
   - Tipo: **Desktop app**
   - Download JSON

### 2. Salvar Credenciais

```bash
mkdir -p secrets/
mv ~/Downloads/credentials.json secrets/google-credentials.json
```

### 3. Primeira Autenticação

```bash
# Rode o calendar server standalone
python packages/mcp_servers/calendar_server/server.py

# Isso abrirá o navegador para autorizar
# Após autorizar, token.json será salvo automaticamente
```

### 4. Atualizar .env

```bash
GOOGLE_CALENDAR_CREDENTIALS_JSON=./secrets/google-credentials.json
GOOGLE_CALENDAR_ID=comercial@alabia.com
```

---

## 🧪 Testes

### Test Chat Endpoint

```bash
# Pergunta simples
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5511999999999",
    "message": "Oi, tudo bem?",
    "context": {"name": "João"}
  }'

# Pergunta sobre preços (vai usar file_search)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5511999999999",
    "message": "Quanto custa o plano enterprise e o que inclui?",
    "context": {"name": "Maria", "email": "maria@empresa.com"}
  }'

# Agendamento (vai usar check_availability e create_event)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5511999999999",
    "message": "Quero agendar uma reunião amanhã às 14h",
    "context": {"name": "Pedro", "email": "pedro@empresa.com"}
  }'
```

---

## 📊 Monitoramento

### Logs

```bash
# Development
# Logs aparecem no terminal

# Docker
docker-compose logs -f orchestrator
docker-compose logs -f chroma

# Filtrar por nível
docker-compose logs orchestrator | grep ERROR
```

### Health Checks

```bash
# API principal
curl http://localhost:8000/health

# Chat module
curl http://localhost:8000/api/chat/health

# ChromaDB
curl http://localhost:8001/api/v1/heartbeat
```

### Métricas RAG

```python
# Python shell
from packages.mcp_servers.rag_server.server import RAGClient

client = RAGClient(chroma_persist_dir="./data/chroma_db")
stats = client.get_stats()
print(stats)
# {'collection_name': 'alabia_docs', 'document_count': 47, 'status': 'ready'}
```

---

## 🔄 Updates

### Atualizar código

```bash
# Pull latest
git pull

# Development
# Uvicorn com --reload já detecta mudanças

# Docker
docker-compose restart orchestrator
```

### Reindexar documentos

```bash
# Limpar e reindexar
python packages/rag/ingest.py docs/comercial/ --clear
```

---

## 🆘 Troubleshooting

### Erro: "ANTHROPIC_API_KEY not set"

```bash
# Verifique .env
cat .env | grep ANTHROPIC

# Se vazio, adicione:
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

### Erro: "Collection not found" (RAG)

```bash
# Indexe os documentos primeiro
python packages/rag/ingest.py docs/comercial/
```

### Erro: "Port 8000 already in use"

```bash
# Encontrar processo
lsof -ti:8000

# Matar processo
kill -9 $(lsof -ti:8000)

# Ou usar outra porta
uvicorn apps.orchestrator.main:app --port 8001
```

### Docker: Container não sobe

```bash
# Ver logs
docker-compose logs orchestrator

# Rebuildar
docker-compose build --no-cache
docker-compose up -d
```

---

## 📚 Próximos Passos

1. **Integração WhatsApp**: Ver [WHATSAPP_INTEGRATION.md](./WHATSAPP_INTEGRATION.md)
2. **Deploy AWS**: Ver [AWS_DEPLOY.md](./AWS_DEPLOY.md)
3. **Customização**: Ver [CUSTOMIZATION.md](./CUSTOMIZATION.md)

---

**Dúvidas?** Abra uma issue ou contate o time interno da Alabia.
