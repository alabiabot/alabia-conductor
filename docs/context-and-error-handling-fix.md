# 🔧 Fix: Context Handling + Error Handling

## Problemas Identificados

### Problema 1: Contexto Limitado

**Sintoma:**
```
User (msg 5): "financeiro@alabia.com.br"
...
User (msg 12): "o mesmo"
Agent: Tentou usar "5511947163792" como email ❌
```

**Causa:**
- Backend WhatsApp enviava apenas últimas 2 mensagens (`limit: 2`)
- Email estava na mensagem 5, fora do contexto
- Agent não sabia qual era "o mesmo" email

### Problema 2: Error Handling Quebrado

**Sintoma:**
```
ERROR: Invalid attendee email
Traceback...
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Causa:**
- Calendar server retornava erro como string plana: `"ERROR: Invalid email"`
- MCP client esperava JSON válido
- JSON parsing falhava e quebrava o fluxo

---

## Soluções Implementadas

### Solução 1A: Prompt Instruindo Uso do Context

**Arquivo:** `packages/llm/prompts.py`

Adicionado no prompt:

```python
**IMPORTANTE sobre EMAIL:**
- Se o usuário disser "o mesmo", "esse mesmo", "o que já passei", 
  procure o email no CONTEXTO DO CLIENTE (seção abaixo)
- Se não encontrar email no contexto, peça novamente
- NUNCA use número de telefone como email
- NUNCA invente email
```

### Solução 1B: Context Destacado no System Prompt

**Arquivo:** `apps/orchestrator/routes/chat.py`

Modificado `_build_system_prompt()` para destacar o email:

```python
if context.email:
    user_info.append(
        f"**Email: {context.email}** ← USE ESTE EMAIL quando o cliente disser 'o mesmo'"
    )

base_prompt += "\n\n**⚠️ IMPORTANTE: Quando o cliente disser 'o mesmo email', " \
               "use o email acima. NUNCA use telefone como email!**"
```

Agora o system prompt ficará assim:

```
## 👤 INFORMAÇÕES DO CLIENTE
- Nome: João Silva
- **Email: financeiro@alabia.com.br** ← USE ESTE EMAIL quando o cliente disser 'o mesmo'
- Telefone: 5511947163792

⚠️ IMPORTANTE: Quando o cliente disser 'o mesmo email', use o email acima. 
NUNCA use telefone como email!
```

### Solução 2A: Calendar Server Retorna JSON em Erros

**Arquivo:** `packages/mcp_servers/calendar_server/server.py`

**Antes (Bugado):**
```python
except Exception as e:
    return [TextContent(type="text", text=f"ERROR: {str(e)}")]  # ❌ String plana
```

**Depois (Correto):**
```python
except Exception as e:
    error_result = {
        "error": str(e),
        "tool": name,
        "arguments": arguments
    }
    return [TextContent(type="text", text=json.dumps(error_result))]  # ✅ JSON válido
```

### Solução 2B: MCP Client Trata Erros Gracefully

**Arquivo:** `apps/orchestrator/mcp_client.py`

**Antes (Bugado):**
```python
parsed_result = json.loads(text_content)  # ❌ Quebra se não for JSON
return parsed_result
```

**Depois (Correto):**
```python
try:
    parsed_result = json.loads(text_content)
except json.JSONDecodeError:
    # Trata como erro
    parsed_result = {"error": text_content, "tool": tool_name}

# Verifica se resultado contém erro
if isinstance(parsed_result, dict) and "error" in parsed_result:
    logger.error(f"Tool error: {parsed_result['error']}")
    return parsed_result  # ✅ Retorna erro para o Claude processar

return parsed_result
```

Agora quando uma tool retorna erro:
1. ✅ Não quebra o JSON parsing
2. ✅ Error é retornado como dict `{"error": "..."}`
3. ✅ Claude recebe o erro e pode responder ao usuário adequadamente
4. ✅ Usuário recebe mensagem clara ao invés de crash

---

## Comportamento Esperado Agora

### Cenário 1: "o mesmo email" com Context

```
User: "Quero agendar para segunda 17h"
Agent: [calls check_availability] "17h está livre. Qual seu email?"

User: "financeiro@alabia.com.br"
Agent: "Perfeito! Agendando..."

# Backend envia context.email = "financeiro@alabia.com.br"

User: "Na verdade quero terça 17h"
Agent: [calls check_availability] "Terça 17h também está livre"

User: "o mesmo email"
Agent: [vê email no context] ✅ Usa "financeiro@alabia.com.br"
Agent: "✅ Agendado para terça 17h! Convite enviado."
```

### Cenário 2: Error Handling

```
User: "Agendar para segunda 17h, email: teste@invalido"
Agent: [calls create_event with invalid email]
Server: {"error": "Invalid attendee email"}
Agent: ✅ "Esse email parece inválido. Pode confirmar o email correto?"

# Antes quebrava com JSONDecodeError
# Agora trata gracefully
```

---

## Recomendações para Backend WhatsApp

### 1. Aumentar Limite de Mensagens

**Atual:**
```python
previous_messages = conversation[-2:]  # ❌ Apenas 2 mensagens
```

**Recomendado:**
```python
previous_messages = conversation[-20:]  # ✅ Últimas 20 mensagens
```

### 2. Extrair e Salvar Informações no Context

**Implementação Sugerida:**

```python
import re

class ConversationManager:
    def __init__(self):
        self.conversations = {}  # user_id -> {history, context}
    
    def process_message(self, user_id, message, response):
        """Process new message and update context"""
        
        # Get or create conversation
        if user_id not in self.conversations:
            self.conversations[user_id] = {
                "history": [],
                "context": {"email": None, "name": None, "phone": user_id}
            }
        
        conv = self.conversations[user_id]
        
        # Extract email from message if present
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            conv["context"]["email"] = email_match.group(0)
        
        # Extract name if present (simple heuristic)
        if "meu nome é" in message.lower():
            name = message.split("meu nome é")[-1].strip()
            conv["context"]["name"] = name
        
        # Update history
        conv["history"].append({"role": "user", "content": message})
        conv["history"].append({"role": "assistant", "content": response})
        
        # Keep only last 20 messages
        conv["history"] = conv["history"][-20:]
        
        return conv
    
    def build_request(self, user_id, message):
        """Build API request with context and history"""
        conv = self.conversations.get(user_id, {"history": [], "context": {}})
        
        return {
            "user_id": user_id,
            "message": message,
            "context": {
                **conv["context"],
                "previous_messages": conv["history"]
            }
        }
```

**Uso:**

```python
manager = ConversationManager()

# User sends message
response = requests.post(CONDUCTOR_API, json=manager.build_request(user_id, message))

# Update conversation with response
manager.process_message(user_id, message, response["response"])
```

### 3. Limpar Conversas Antigas

```python
from datetime import datetime, timedelta

class ConversationManager:
    def __init__(self, timeout_minutes=30):
        self.conversations = {}
        self.last_activity = {}  # user_id -> timestamp
        self.timeout = timedelta(minutes=timeout_minutes)
    
    def cleanup_old_conversations(self):
        """Remove conversations older than timeout"""
        now = datetime.now()
        to_remove = []
        
        for user_id, last_time in self.last_activity.items():
            if now - last_time > self.timeout:
                to_remove.append(user_id)
        
        for user_id in to_remove:
            del self.conversations[user_id]
            del self.last_activity[user_id]
    
    def process_message(self, user_id, message, response):
        self.last_activity[user_id] = datetime.now()
        # ... rest of implementation
```

---

## Arquivos Modificados

### 1. `packages/llm/prompts.py`
- Linhas 59-63: Adicionadas regras sobre uso de email do context

### 2. `apps/orchestrator/routes/chat.py`
- Linhas 179-185: Context destacando email com instruções

### 3. `packages/mcp_servers/calendar_server/server.py`
- Linhas 346-371: Error handling retornando JSON válido

### 4. `apps/orchestrator/mcp_client.py`
- Linhas 239-262: Error handling robusto com JSON parsing

---

## Testing

### Test 1: Context com "o mesmo"

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "o mesmo email",
    "context": {
      "email": "teste@alabia.com.br",
      "previous_messages": [
        {"role": "user", "content": "Quero agendar"},
        {"role": "assistant", "content": "Qual horário?"}
      ]
    }
  }'
```

**Esperado:** Agent usa "teste@alabia.com.br"

### Test 2: Error Handling

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "Agendar para hoje 14h, email: INVALIDO"
  }'
```

**Esperado:** Agent responde com mensagem clara sobre email inválido

---

## Checklist

- [x] Prompt instrui uso de email do context
- [x] System prompt destaca email claramente
- [x] Calendar server retorna JSON em erros
- [x] MCP client trata erros gracefully
- [x] Documentação criada
- [ ] Backend WhatsApp implementa extração de email
- [ ] Backend WhatsApp aumenta limite de mensagens
- [ ] Backend WhatsApp implementa cleanup de conversas

---

**Status:** ✅ **CORRIGIDO (Conductor)**
**Pendente:** Backend WhatsApp implementar extração de context
**Data:** 02/Nov/2025
