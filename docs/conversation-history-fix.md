# 🔧 Fix: Conversation History

## Problema Identificado

O agente estava perdendo o contexto entre mensagens, tratando cada requisição como uma conversa nova.

### Evidência do Problema:

```
User: "Hoje tem horário?"
Agent: [checks calendar] "Temos: 9h, 10h, 11h..."

User: "As 11"
Agent: "Perfeito! Qual seu email?"

User: "financeiro@alabia.com.br"
Agent: "Como posso ajudar você hoje?" ❌ PERDEU O CONTEXTO!
```

### Logs Mostrando o Problema:

```
11:09:25 - Chat iteration 1/10  # Primeira mensagem
11:09:28 - Chat iteration 2/10  # Chamou check_availability

11:09:55 - Chat iteration 1/10  # Segunda mensagem - REINICIOU! ❌
```

Cada nova mensagem estava iniciando em "iteration 1/10", indicando que o histórico não estava sendo passado.

---

## Causa Raiz

O endpoint `/api/chat` não estava usando o campo `previous_messages` do contexto.

### Código Anterior (Bugado):

```python
# apps/orchestrator/routes/chat.py

result = await anthropic_driver.chat_with_tools(
    user_message=request.message,  # ❌ Apenas mensagem atual
    system=system_prompt,
    tools=anthropic_tools,
    tool_executor=mcp_orchestrator.execute_tool
    # ❌ conversation_history não estava sendo passado!
)
```

### Problema:

- O `ChatRequest` tinha o campo `context.previous_messages` (linha 26)
- Mas esse campo nunca era usado no processamento
- Cada mensagem era tratada como início de nova conversa

---

## Solução Implementada

### 1. Adicionar Construção do Histórico

```python
# apps/orchestrator/routes/chat.py (linha 93-96)

# 4. Build conversation history from context
conversation_history = []
if request.context and request.context.previous_messages:
    conversation_history = _build_conversation_history(request.context.previous_messages)
```

### 2. Passar Histórico para o Driver

```python
# apps/orchestrator/routes/chat.py (linha 99-105)

result = await anthropic_driver.chat_with_tools(
    user_message=request.message,
    system=system_prompt,
    tools=anthropic_tools,
    tool_executor=mcp_orchestrator.execute_tool,
    conversation_history=conversation_history  # ✅ Agora passa o histórico!
)
```

### 3. Converter Formato

```python
# apps/orchestrator/routes/chat.py (linha 129-148)

def _build_conversation_history(previous_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Converte previous_messages para formato Anthropic
    
    Expected format:
    [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
    ]
    """
    history = []
    for msg in previous_messages:
        role = msg.get("role", "user")
        content = msg.get("content", msg.get("text", ""))
        
        if role and content:
            history.append({"role": role, "content": content})
    
    return history
```

---

## Como o Backend WhatsApp Deve Usar

### Estrutura de Dados:

O backend WhatsApp deve manter o histórico de cada usuário e enviá-lo em cada requisição:

```python
# Exemplo: Backend WhatsApp mantém histórico por user_id
conversations = {}  # user_id -> list of messages

def handle_message(user_id, message):
    # 1. Get conversation history
    history = conversations.get(user_id, [])
    
    # 2. Call API with history
    response = requests.post("http://conductor:8000/api/chat", json={
        "user_id": user_id,
        "message": message,
        "context": {
            "previous_messages": history  # ✅ Envia histórico!
        }
    })
    
    # 3. Update history
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response["response"]})
    conversations[user_id] = history
    
    return response
```

### Exemplo de Requisição Completa:

```json
{
  "user_id": "5511947163792",
  "message": "financeiro@alabia.com.br",
  "context": {
    "previous_messages": [
      {"role": "user", "content": "Hoje tem horário?"},
      {"role": "assistant", "content": "Temos: 9h, 10h, 11h, 12h..."},
      {"role": "user", "content": "As 11"},
      {"role": "assistant", "content": "Perfeito! Qual seu email?"}
    ]
  }
}
```

---

## Testando a Correção

### Script de Teste:

```bash
python test_agent_behavior.py
```

### Comportamento Esperado:

```
USER: Hoje tem horário?
AGENT: [calls check_availability] Temos: 9h, 10h, 11h...

USER: As 11
AGENT: Perfeito! Qual seu email?

USER: financeiro@alabia.com.br
AGENT: [calls create_event] ✅ Agendado para hoje 11h!
```

### O Que Deve Acontecer:

1. **Primeira mensagem**: Agent checa disponibilidade
2. **Segunda mensagem**: Agent lembra do contexto (11h)
3. **Terceira mensagem**: Agent cria o evento com email + horário

### ❌ Comportamento Antigo (Bugado):

```
USER: financeiro@alabia.com.br
AGENT: Como posso ajudar você hoje?  # ❌ Perdeu contexto!
```

### ✅ Comportamento Novo (Correto):

```
USER: financeiro@alabia.com.br
AGENT: ✅ Agendado para hoje 11h! Convite enviado.
```

---

## Impacto

### Antes da Correção:
- ❌ Usuário precisa repetir informações
- ❌ Fluxo de agendamento quebrado
- ❌ UX ruim
- ❌ Parece que o agent "tem amnésia"

### Depois da Correção:
- ✅ Conversa fluida e natural
- ✅ Agent lembra de tudo que foi dito
- ✅ Agendamentos completam sem repetição
- ✅ UX profissional

---

## Logs de Validação

### Comportamento Correto:

```
11:30:00 - Chat iteration 1/5  # User: "Hoje tem horário?"
11:30:02 - Chat iteration 2/5  # Tool: check_availability
11:30:05 - Chat iteration 1/5  # User: "As 11" (com histórico)
11:30:07 - Chat iteration 1/5  # User: "email@..." (com histórico)
11:30:09 - Chat iteration 2/5  # Tool: create_event ✅
```

Note que as iterações reiniciam (é esperado), mas o contexto é preservado através do `conversation_history`.

---

## Arquivos Modificados

- `apps/orchestrator/routes/chat.py`:
  - Linha 93-96: Build conversation history
  - Linha 104: Pass history to driver
  - Linha 129-148: Função `_build_conversation_history()`

---

## Checklist para Backend WhatsApp

- [ ] Implementar armazenamento de histórico por `user_id`
- [ ] Enviar `context.previous_messages` em TODAS as requisições
- [ ] Limpar histórico após timeout (ex: 30 minutos sem interação)
- [ ] Limitar tamanho do histórico (ex: últimas 20 mensagens)
- [ ] Testar fluxo completo de agendamento

---

**Status:** ✅ **CORRIGIDO**
**Data:** 02/Nov/2025
**Versão:** 1.1
