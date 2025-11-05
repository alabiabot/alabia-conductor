# Pipedrive CRM Integration

## Overview

Automatic lead creation in Pipedrive after scheduling meetings via the chat agent.

## Architecture

```
User Request → Chat Agent → Google Calendar (event) → Pipedrive (lead)
```

The agent automatically creates a lead in Pipedrive after successfully scheduling a meeting, ensuring every scheduled interaction is tracked in the sales funnel.

## Implementation

### 1. Pipedrive MCP Server

**Location:** [packages/mcp_servers/pipedrive_simple/server.py](../packages/mcp_servers/pipedrive_simple/server.py)

**Tool:** `create_lead`

**Workflow:**
1. **Search/Create Person:**
   - Searches for existing person by email using `/persons/search`
   - If found, uses existing `person_id`
   - If not found, creates new person via `/persons`

2. **Create Lead:**
   - Creates lead with `person_id` via `/leads`
   - Sets `visible_to: "3"` for visibility control

3. **Add Note:**
   - Attaches note to lead via `/notes` if provided
   - Note includes meeting details and context

**Parameters:**
```python
{
  "title": str,              # Lead title (e.g., "Reunião - Nome do Cliente")
  "person_name": str,        # Contact name
  "person_email": str,       # Contact email (required for person search/creation)
  "organization_name": str,  # Optional organization name
  "note": str               # Optional note with meeting context
}
```

**Returns:**
```python
{
  "lead_id": str,           # UUID of created lead
  "person_id": int,         # ID of person (created or existing)
  "title": str,             # Lead title
  "person_email": str,      # Contact email
  "url": str                # Direct link to lead in Pipedrive inbox
}
```

### 2. MCP Orchestrator Connection

**Location:** [apps/orchestrator/mcp_client.py](../apps/orchestrator/mcp_client.py:190-240)

Added `_connect_pipedrive_server()` method to initialize Pipedrive MCP server alongside RAG and Calendar servers.

```python
async def _connect_pipedrive_server(self):
    """Conecta ao Pipedrive MCP Server"""
    server_script = project_root / "packages" / "mcp_servers" / "pipedrive_simple" / "server.py"
    # ... stdio connection setup
```

### 3. Agent Prompt Update

**Location:** [packages/llm/prompts.py](../packages/llm/prompts.py:102-113)

Updated system prompt to instruct agent to **automatically call** `create_lead` after creating calendar events:

```
### create_lead
**Quando usar:** SEMPRE após criar evento (create_event)

**⚠️ IMPORTANTE - AUTOMAÇÃO DE VENDAS:**
Após criar um evento com create_event, SEMPRE chame create_lead para registrar no CRM:
1. Cria evento → create_event
2. Registra lead → create_lead (AUTOMATICAMENTE!)

**Exemplo:**
Cliente dá email → create_event → create_lead
Note: "Reunião agendada para [data/hora]. Interesse em [assunto]"
```

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Pipedrive Configuration
PIPEDRIVE_API_TOKEN=your_api_token_here
PIPEDRIVE_COMPANY_DOMAIN=your_company_domain
```

**How to get credentials:**
1. Login to Pipedrive
2. Go to Settings → Personal → API
3. Copy your API token
4. Your domain is the subdomain in your Pipedrive URL: `https://{domain}.pipedrive.com`

### Verify Installation

Check tool is registered:
```bash
curl http://localhost:8000/chat/health
```

Should show `create_lead` in tools list:
```json
{
  "mcp": {
    "tools": ["file_search", "create_event", "check_availability", "list_events", "cancel_event", "create_lead"]
  }
}
```

## Testing

### Unit Test

Run isolated test:
```bash
source venv/bin/activate
python test_pipedrive_integration.py
```

**Expected output:**
```
✅ Initialized with 7 tools
✅ create_lead tool found!
✅ Lead created successfully!
📋 Lead ID: b4497070-b858-11f0-bd42-cf514cd2ab3c
🔗 URL: https://alabia.pipedrive.com/leads/inbox/b4497070-b858-11f0-bd42-cf514cd2ab3c
```

### Integration Test (via chat)

1. Start FastAPI server:
```bash
uvicorn apps.orchestrator.main:app --reload
```

2. Send chat request:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5511999999999",
    "message": "Quero agendar para amanhã 14h",
    "context": {
      "name": "João Silva",
      "email": "joao@empresa.com"
    }
  }'
```

3. Agent should:
   - ✅ Check availability for tomorrow
   - ✅ Create calendar event at 14h with Google Meet link
   - ✅ **Automatically create lead in Pipedrive**
   - ✅ Return confirmation with meeting link

4. Verify in Pipedrive:
   - Go to Leads → Inbox
   - Should see new lead: "Reunião - João Silva"
   - Contact: João Silva (joao@empresa.com)
   - Note: "Reunião agendada para [date] 14:00. Interesse em [context]"

## Agent Behavior

### Automatic Flow

When user schedules a meeting, the agent executes:

```
1. check_availability("2025-11-04")
2. create_event(title="...", start_datetime="2025-11-04T14:00:00-03:00", attendee_email="joao@empresa.com")
   → Returns: event_id, meet_link
3. create_lead(title="Reunião - João Silva", person_name="João Silva", person_email="joao@empresa.com", note="Reunião agendada para 2025-11-04 14:00")
   → Returns: lead_id, url
4. Respond to user: "✅ Agendado! 🎥 Link: [meet_link]"
```

**No manual intervention needed** - the agent handles CRM registration automatically.

### Error Handling

If Pipedrive API fails:
- Agent receives error in JSON format
- Error is logged but doesn't block confirmation
- User still receives meeting confirmation
- Admin can check logs and manually create lead

Example error response:
```json
{
  "error": "Pipedrive not configured",
  "tool": "create_lead"
}
```

## API Reference

### Pipedrive Endpoints Used

1. **Search Person by Email**
   ```
   GET /v1/persons/search?term={email}&fields=email
   ```

2. **Create Person**
   ```
   POST /v1/persons
   Body: {"name": "...", "email": ["..."]}
   ```

3. **Create Lead**
   ```
   POST /v1/leads
   Body: {"title": "...", "person_id": 123, "visible_to": "3"}
   ```

4. **Add Note to Lead**
   ```
   POST /v1/notes
   Body: {"content": "...", "lead_id": "uuid"}
   ```

## Troubleshooting

### Lead not appearing in Pipedrive

**Check:**
1. Environment variables set correctly in `.env`
2. API token has `leads:full` permission
3. Check orchestrator logs for API errors
4. Verify test script works: `python test_pipedrive_integration.py`

### Duplicate persons created

**Cause:** Email search not finding existing person

**Solution:** Pipedrive search is case-sensitive and requires exact match. The implementation searches first to avoid duplicates.

### 400 Bad Request error

**Common causes:**
- ❌ `"person" is not allowed` → Leads API doesn't accept nested person object
- ❌ `"person_name" is not allowed` → Leads API requires `person_id`, not inline person data
- ✅ **Solution:** Create person first, then use `person_id` in lead (already implemented)

## Files Modified

| File | Changes |
|------|---------|
| [packages/mcp_servers/pipedrive_simple/server.py](../packages/mcp_servers/pipedrive_simple/server.py) | Created Pipedrive MCP server with `create_lead` tool |
| [apps/orchestrator/mcp_client.py](../apps/orchestrator/mcp_client.py) | Added `_connect_pipedrive_server()` to initialization |
| [packages/llm/prompts.py](../packages/llm/prompts.py) | Added automatic lead creation instructions |
| [.env](.env) | Added `PIPEDRIVE_API_TOKEN` and `PIPEDRIVE_COMPANY_DOMAIN` |
| [test_pipedrive_integration.py](../test_pipedrive_integration.py) | Created integration test script |

## Next Steps

### Backend WhatsApp Integration

To complete the sales automation flow, the WhatsApp backend should:

1. **Extract contact info from early messages:**
   ```python
   # When user provides name/email in conversation
   if email_detected:
       context["email"] = extract_email(message)
   if name_detected:
       context["name"] = extract_name(message)
   ```

2. **Pass enriched context to chat endpoint:**
   ```python
   {
       "user_id": whatsapp_number,
       "message": current_message,
       "context": {
           "name": stored_name,
           "email": stored_email,
           "phone": whatsapp_number,
           "previous_messages": last_20_messages  # For context
       }
   }
   ```

3. **Store meeting confirmations:**
   - Save `event_id` and `lead_id` to database
   - Link to WhatsApp conversation for reference

### Optional Enhancements

1. **Add organization field:** Currently defaults to "Alabia", could detect company name from conversation
2. **Custom fields:** Map additional lead data (source, interest level, etc.)
3. **Lead labeling:** Automatically tag leads based on conversation content
4. **Activity tracking:** Log WhatsApp messages as activities in Pipedrive
5. **Deal conversion:** When lead advances, automatically convert to deal

## Success Metrics

Track in logs/monitoring:
- ✅ Leads created automatically: `INFO: Tool create_lead executed successfully`
- ✅ Lead creation rate: `created_leads / scheduled_meetings * 100%`
- ⚠️ Lead creation failures: `ERROR: Tool create_lead returned error`

**Target:** 100% of scheduled meetings should generate leads (unless Pipedrive is unavailable).
