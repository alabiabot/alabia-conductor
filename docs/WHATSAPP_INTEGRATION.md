# 📱 Integração WhatsApp - Alabia Conductor

Guia para integrar o Conductor com backend WhatsApp da Alabia.

---

## 🏗️ Arquitetura

```
WhatsApp Business API
        ↓
Backend WhatsApp (Alabia)  ← Já existe
        ↓ HTTP POST
Conductor API (/api/chat)
        ↓
Claude + MCP Tools
        ↓ Response
Backend WhatsApp
        ↓
WhatsApp → Cliente
```

---

## 📡 Endpoint de Integração

### POST /api/chat

**URL**: `https://your-conductor-host.com/api/chat`

**Headers**:
```
Content-Type: application/json
# Opcional: Authorization para segurança
# Authorization: Bearer YOUR_SECRET_TOKEN
```

**Request Body**:
```json
{
  "user_id": "5511999999999",
  "message": "Quero agendar uma reunião",
  "context": {
    "name": "João Silva",
    "email": "joao@empresa.com",
    "phone": "5511999999999",
    "previous_messages": [
      {"role": "user", "content": "Oi"},
      {"role": "assistant", "content": "Olá! Como posso ajudar?"}
    ],
    "metadata": {
      "source": "whatsapp",
      "conversation_id": "conv_123"
    }
  }
}
```

**Response**:
```json
{
  "response": "Ótimo! Temos disponibilidade amanhã às 14h e 16h. Qual prefere?",
  "actions": [
    {
      "tool": "check_availability",
      "status": "success",
      "result": {
        "available_slots": ["14:00", "16:00"],
        "date": "2025-11-01"
      },
      "error": null
    }
  ],
  "needs_followup": true,
  "metadata": {
    "user_id": "5511999999999",
    "tools_used": ["check_availability"],
    "iterations": 2
  }
}
```

---

## 🔗 Implementação no Backend WhatsApp

### Node.js / Express

```javascript
const axios = require('axios');

const CONDUCTOR_URL = process.env.CONDUCTOR_API_URL;
const CONDUCTOR_TOKEN = process.env.CONDUCTOR_API_TOKEN;

async function processMessage(whatsappMessage) {
  try {
    // Monta request para Conductor
    const request = {
      user_id: whatsappMessage.from,
      message: whatsappMessage.body,
      context: {
        name: whatsappMessage.contact?.name,
        phone: whatsappMessage.from,
        metadata: {
          source: 'whatsapp',
          conversation_id: whatsappMessage.conversation_id
        }
      }
    };

    // Chama Conductor
    const response = await axios.post(
      `${CONDUCTOR_URL}/api/chat`,
      request,
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${CONDUCTOR_TOKEN}`
        },
        timeout: 60000 // 60s timeout
      }
    );

    // Envia resposta para WhatsApp
    const { response: aiResponse, actions, needs_followup } = response.data;

    await sendWhatsAppMessage(whatsappMessage.from, aiResponse);

    // Salva contexto se needs_followup
    if (needs_followup) {
      await saveConversationContext(whatsappMessage.from, {
        last_message: aiResponse,
        awaiting_response: true
      });
    }

    // Log actions executadas
    if (actions.length > 0) {
      console.log('Actions executed:', actions.map(a => a.tool));
    }

  } catch (error) {
    console.error('Error calling Conductor:', error);

    // Fallback
    await sendWhatsAppMessage(
      whatsappMessage.from,
      'Desculpe, estou com dificuldades no momento. Tente novamente em instantes.'
    );
  }
}
```

### Python / FastAPI

```python
import httpx
from fastapi import FastAPI, HTTPException

CONDUCTOR_URL = os.getenv("CONDUCTOR_API_URL")
CONDUCTOR_TOKEN = os.getenv("CONDUCTOR_API_TOKEN")

async def process_whatsapp_message(message: WhatsAppMessage):
    """Processa mensagem do WhatsApp via Conductor"""

    # Monta request
    request = {
        "user_id": message.from_number,
        "message": message.body,
        "context": {
            "name": message.contact_name,
            "phone": message.from_number,
            "metadata": {
                "source": "whatsapp",
                "message_id": message.id
            }
        }
    }

    # Chama Conductor
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{CONDUCTOR_URL}/api/chat",
                json=request,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {CONDUCTOR_TOKEN}"
                },
                timeout=60.0
            )
            response.raise_for_status()

            data = response.json()

            # Envia resposta
            await send_whatsapp_message(
                to=message.from_number,
                text=data["response"]
            )

            return data

        except httpx.HTTPError as e:
            logger.error(f"Error calling Conductor: {e}")

            # Fallback
            await send_whatsapp_message(
                to=message.from_number,
                text="Desculpe, tive um problema. Tente novamente."
            )
            raise HTTPException(status_code=500, detail=str(e))
```

---

## 🔐 Segurança

### 1. Autenticação via Bearer Token

**No Conductor** (adicionar middleware):

```python
# apps/orchestrator/middleware/auth.py
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials

    expected_token = os.getenv("API_AUTH_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Auth not configured")

    if token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    return True

# Em apps/orchestrator/routes/chat.py
from apps.orchestrator.middleware.auth import verify_token

@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_token)])
async def chat(request: ChatRequest):
    ...
```

**No Backend WhatsApp**:
```bash
# .env
CONDUCTOR_API_TOKEN=seu-token-secreto-aqui
```

### 2. Rate Limiting

Já configurado no `nginx.conf`:
```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req zone=api_limit burst=20 nodelay;
```

### 3. IP Whitelist (Opcional)

```nginx
# nginx.conf
geo $whatsapp_backend {
    default 0;
    192.168.1.100 1;  # IP do backend WhatsApp
    10.0.0.0/8 1;     # Rede interna
}

server {
    location /api/ {
        if ($whatsapp_backend = 0) {
            return 403;
        }
        proxy_pass http://orchestrator;
    }
}
```

---

## 🧪 Testes de Integração

### 1. Teste Manual

```bash
# Simula chamada do backend WhatsApp
curl -X POST https://conductor.alabia.com/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "user_id": "5511999999999",
    "message": "Quanto custa o plano starter?",
    "context": {
      "name": "Cliente Teste",
      "phone": "5511999999999",
      "metadata": {"source": "whatsapp"}
    }
  }'
```

### 2. Teste Automatizado

```python
import pytest
import httpx

CONDUCTOR_URL = "https://conductor.alabia.com"
API_TOKEN = "your-token"

@pytest.mark.asyncio
async def test_whatsapp_integration():
    """Testa integração WhatsApp → Conductor"""

    async with httpx.AsyncClient() as client:
        # Simula mensagem WhatsApp
        response = await client.post(
            f"{CONDUCTOR_URL}/api/chat",
            json={
                "user_id": "5511999999999",
                "message": "Oi",
                "context": {"name": "Teste"}
            },
            headers={"Authorization": f"Bearer {API_TOKEN}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "response" in data
        assert isinstance(data["response"], str)
        assert len(data["response"]) > 0

        print(f"✓ Response: {data['response']}")
```

---

## 📊 Monitoramento

### Logs Estruturados

```python
# No backend WhatsApp, log cada interação
logger.info("whatsapp_to_conductor", extra={
    "user_id": user_id,
    "message_length": len(message),
    "response_time_ms": elapsed_ms,
    "tools_used": tools_used,
    "success": True
})
```

### Métricas

- **Taxa de sucesso**: % de chamadas bem-sucedidas
- **Tempo de resposta**: Latência média
- **Tools mais usadas**: Quais ferramentas são mais acionadas
- **Erros**: Taxa de erro por tipo

---

## 🔄 Fluxos Comuns

### Fluxo 1: Pergunta Simples
```
User: "Oi"
  → Conductor: Responde com saudação
  → WhatsApp: Envia resposta
```

### Fluxo 2: Consulta com RAG
```
User: "Quanto custa o plano pro?"
  → Conductor:
      1. Usa file_search para buscar preços
      2. Claude formula resposta com dados encontrados
  → WhatsApp: Envia resposta com preço
```

### Fluxo 3: Agendamento Multi-turn
```
Turn 1:
User: "Quero agendar reunião"
  → Conductor: "Quando prefere?"
  → WhatsApp: Envia pergunta

Turn 2:
User: "Amanhã às 14h"
  → Conductor:
      1. check_availability("2025-11-01")
      2. Verifica se 14h está livre
      3. Pede confirmação
  → WhatsApp: "Confirma reunião 01/11 às 14h?"

Turn 3:
User: "Sim, confirmo"
  → Conductor:
      1. create_event(...)
      2. Cria evento no Calendar
  → WhatsApp: "✓ Reunião agendada! Você receberá um email."
```

---

## 🚨 Tratamento de Erros

### No Backend WhatsApp

```javascript
try {
  const result = await callConductor(message);
  await sendResponse(result.response);
} catch (error) {
  if (error.code === 'ETIMEDOUT') {
    // Timeout
    await sendResponse("Desculpe, estou demorando mais que o normal. Tente novamente.");
  } else if (error.response?.status === 429) {
    // Rate limit
    await sendResponse("Muitas mensagens ao mesmo tempo. Aguarde um momento.");
  } else {
    // Erro genérico
    await sendResponse("Desculpe, tive um problema. Nossa equipe já foi notificada.");
    await notifyDevTeam(error);
  }
}
```

---

## 📚 Referências

- [API Reference](./API_REFERENCE.md)
- [Anthropic Claude Docs](https://docs.anthropic.com)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)

---

**Dúvidas?** Contate o time de desenvolvimento da Alabia.
