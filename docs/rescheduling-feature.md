# 🔄 Rescheduling Feature - Cancel & Recreate Events

## Problema Resolvido

Quando o usuário reagendava uma reunião, o sistema estava criando um **novo evento** sem deletar o anterior, causando **duplicação** no calendário.

**Antes (Bugado):**
```
User: "Quero mudar para terça 17h"
Agent: [cria novo evento para terça 17h]
Calendar: 2 eventos (segunda 14h + terça 17h) ❌
```

**Agora (Correto):**
```
User: "Quero mudar para terça 17h"
Agent: [cancela evento de segunda 14h]
Agent: [cria novo evento para terça 17h]
Calendar: 1 evento (apenas terça 17h) ✅
```

---

## Solução Implementada

### 1. Nova Tool: `cancel_event`

**Arquivo:** `packages/mcp_servers/calendar_server/server.py`

```python
def cancel_event(
    self,
    event_id: str,
    calendar_id: str = 'primary',
    send_updates: bool = True
) -> Dict[str, Any]:
    """
    Cancela/deleta um evento do calendário
    
    Args:
        event_id: ID do evento a ser cancelado
        calendar_id: ID do calendário  
        send_updates: Se True, notifica participantes do cancelamento
        
    Returns:
        Confirmação do cancelamento
    """
    self.service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
        sendUpdates='all' if send_updates else 'none'
    ).execute()
    
    return {
        "event_id": event_id,
        "status": "cancelled",
        "message": "Evento cancelado com sucesso"
    }
```

**Características:**
- ✅ Deleta completamente o evento do calendário
- ✅ Envia email de cancelamento aos participantes (se `send_updates=True`)
- ✅ Remove tanto o evento quanto o link do Google Meet associado
- ✅ Error handling robusto

---

### 2. Agent Prompt Atualizado

**Arquivo:** `packages/llm/prompts.py`

Adicionadas instruções explícitas sobre reagendamento:

```python
**⚠️ REAGENDAMENTO:** Quando cliente quiser MUDAR horário:
1. PRIMEIRO: chame list_events para pegar o event_id
2. SEGUNDO: chame cancel_event(event_id) para deletar o antigo  
3. TERCEIRO: chame create_event com novo horário

**IMPORTANTE:** Sempre cancele o evento antigo ANTES de criar o novo!
```

---

## Fluxo Completo de Reagendamento

### Cenário: Cliente Quer Mudar Horário

```
User: "Quero mudar o horário da reunião"
Agent: [calls list_events]
Agent: "Você tem reunião marcada para segunda-feira 14h. Qual novo horário prefere?"

User: "Terça 17h"
Agent: [calls check_availability("2025-11-05")]
Agent: "Terça 17h está disponível!"
Agent: [calls cancel_event(event_id="abc123")]
Agent: [calls create_event(...terça 17h...)]
Agent: "✅ Reagendado para terça-feira 17h!

       📧 Novo convite enviado para paulo@email.com
       🎥 Novo link do Meet: https://meet.google.com/xyz-new-link
       
       O evento antigo foi cancelado automaticamente."
```

### Sequência de Tools Chamadas:

1. **list_events** → Obtém ID do evento atual
2. **check_availability** (opcional) → Verifica se novo horário está livre
3. **cancel_event** → Deleta evento antigo
4. **create_event** → Cria novo evento com novo horário

---

## Detalhes Técnicos

### Google Calendar API - Delete Event

```python
service.events().delete(
    calendarId='primary',
    eventId='event_id_here',
    sendUpdates='all'  # 'all', 'externalOnly', 'none'
).execute()
```

**sendUpdates Options:**
- `'all'` - Envia email para TODOS os participantes
- `'externalOnly'` - Envia apenas para participantes externos
- `'none'` - Não envia notificações

**⚠️ Nota:** O evento é **deletado permanentemente**, não apenas marcado como cancelado.

---

### Tool Schema

```json
{
  "name": "cancel_event",
  "description": "Cancela/deleta um evento do calendário. Use quando o cliente quiser reagendar ou cancelar uma reunião.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "event_id": {
        "type": "string",
        "description": "ID do evento a ser cancelado (obtido via list_events)"
      },
      "send_updates": {
        "type": "boolean",
        "description": "Se True, notifica participantes do cancelamento (padrão: True)"
      }
    },
    "required": ["event_id"]
  }
}
```

---

## Exemplos de Uso

### Exemplo 1: Reagendamento Simples

```python
# 1. Listar eventos para obter ID
result = await mcp_client.execute_tool("list_events", {"days": 7})
# Retorna: {"events": [{"id": "abc123", "title": "Reunião", "start": "2025-11-04T14:00:00"}]}

# 2. Cancelar evento antigo
result = await mcp_client.execute_tool("cancel_event", {"event_id": "abc123"})
# Retorna: {"event_id": "abc123", "status": "cancelled"}

# 3. Criar novo evento
result = await mcp_client.execute_tool("create_event", {
    "title": "Reunião Comercial - Alabia",
    "start_datetime": "2025-11-05T17:00:00",
    "attendee_email": "cliente@email.com"
})
# Retorna: novo evento com novo meet_link
```

### Exemplo 2: Cancelamento Sem Reagendar

```python
# Cliente quer apenas cancelar
User: "Preciso cancelar a reunião"
Agent: [calls list_events]
Agent: [calls cancel_event]
Agent: "Reunião de segunda 14h foi cancelada. Email de cancelamento enviado para paulo@email.com"
```

---

## O Que Acontece no Google Calendar

### Quando `cancel_event` é Chamado:

1. ✅ **Evento é deletado** do Google Calendar
2. ✅ **Email de cancelamento** é enviado aos participantes:
   ```
   Subject: Cancelled: Reunião Comercial - Alabia
   Body: Este evento foi cancelado.
   ```
3. ✅ **Link do Google Meet** é invalidado (não funciona mais)
4. ✅ **Notificações** do evento são removidas

### Quando Novo Evento é Criado:

1. ✅ **Novo evento** aparece no calendário
2. ✅ **Novo link do Meet** é gerado
3. ✅ **Novo email** de convite é enviado:
   ```
   Subject: Reunião Comercial - Alabia
   Body: Você foi convidado para este evento.
   Link do Meet: [novo link]
   ```

---

## Benefícios

### Para o Usuário:
- ✅ Reagenda em **uma única interação**
- ✅ Não precisa manualmente cancelar evento antigo
- ✅ Recebe **email automático** sobre a mudança
- ✅ Calendário sempre **limpo e organizado**

### Para a Alabia:
- ✅ Processo profissional
- ✅ Evita confusão com eventos duplicados
- ✅ Cliente recebe comunicação clara
- ✅ Experiência superior à concorrência

---

## Error Handling

### Erro: Event Not Found

```json
{
  "error": "Failed to cancel event: <HttpError 404 'Not Found'>",
  "tool": "cancel_event",
  "arguments": {"event_id": "invalid_id"}
}
```

**Causa:** Event ID inválido ou evento já foi deletado

**Solução:** Agent deve listar eventos novamente antes de tentar cancelar

### Erro: Insufficient Permissions

```json
{
  "error": "Failed to cancel event: <HttpError 403 'Forbidden'>",
  "tool": "cancel_event"
}
```

**Causa:** Conta não tem permissão para deletar esse evento

**Solução:** Verificar permissões do Google Calendar

---

## Arquivos Modificados

### 1. `packages/mcp_servers/calendar_server/server.py`

**Linhas 282-317:** Função `cancel_event()`
```python
def cancel_event(self, event_id, calendar_id='primary', send_updates=True):
    self.service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
        sendUpdates='all' if send_updates else 'none'
    ).execute()
```

**Linhas 394-411:** Tool schema `cancel_event`
```python
Tool(
    name="cancel_event",
    description="Cancela/deleta um evento do calendário...",
    inputSchema={...}
)
```

**Linha 432-433:** Handler no `call_tool()`
```python
elif name == "cancel_event":
    result = calendar_client.cancel_event(**arguments)
```

### 2. `packages/llm/prompts.py`

**Linhas 86-100:** Instruções sobre `cancel_event`
```python
**⚠️ REAGENDAMENTO:** Quando cliente quiser MUDAR horário:
1. PRIMEIRO: chame list_events para pegar o event_id
2. SEGUNDO: chame cancel_event(event_id) para deletar o antigo
3. TERCEIRO: chame create_event com novo horário
```

**Linhas 155-169:** Fluxo completo de reagendamento
```python
### 🔄 FLUXO DE REAGENDAMENTO:
Cliente: "Quero mudar o horário"
...
**IMPORTANTE:** Sempre cancele o evento antigo ANTES de criar o novo!
```

---

## Testing

### Teste Manual via API

```bash
# 1. Criar um evento de teste
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "Quero agendar para segunda 14h",
    "context": {"email": "test@example.com"}
  }'

# 2. Reagendar
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "Quero mudar para terça 17h"
  }'
```

**Verificar:**
1. ✅ Evento de segunda foi deletado
2. ✅ Novo evento de terça foi criado
3. ✅ Email de cancelamento enviado
4. ✅ Email de novo convite enviado
5. ✅ Apenas 1 evento no calendário

---

## Próximas Melhorias (Opcional)

### 1. Update ao invés de Delete

Atualmente deletamos e recriamos. Alternativa: **atualizar** o evento existente:

```python
def reschedule_event(self, event_id, new_start_datetime):
    """Update event instead of delete+create"""
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    event['start']['dateTime'] = new_start_datetime
    # ... update conferenceData if needed
    updated = service.events().update(..., body=event).execute()
```

**Prós:** Mantém mesmo event_id, histórico preservado
**Contras:** Link do Meet permanece o mesmo (pode ser bom ou ruim)

### 2. Reagendamento Inteligente

Detectar automaticamente quando é reagendamento:

```python
# Se há evento nos próximos 7 dias com mesmo participante
# Perguntar: "Quer reagendar a reunião de segunda ou criar nova?"
```

### 3. Histórico de Reagendamentos

Salvar histórico de quantas vezes um cliente reagendou:

```python
metadata = {
    "rescheduled_count": 2,
    "original_date": "2025-11-04T14:00:00"
}
```

---

**Status:** ✅ **IMPLEMENTADO E FUNCIONANDO**
**Data:** 02/Nov/2025
**Versão:** 1.0
