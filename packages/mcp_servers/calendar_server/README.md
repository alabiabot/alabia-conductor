# Google Calendar MCP Server

MCP Server para integração com Google Calendar.

## Setup

### 1. Criar projeto no Google Cloud

1. Acesse https://console.cloud.google.com
2. Crie um novo projeto ou selecione existente
3. Ative a Google Calendar API
4. Crie credenciais OAuth 2.0:
   - Tipo: Desktop app
   - Download do JSON

### 2. Configurar credenciais

```bash
# Salvar credentials.json
mkdir -p secrets/
mv ~/Downloads/credentials.json secrets/google-credentials.json
```

### 3. Primeira autenticação

```bash
# Rode o server standalone para autenticar
python packages/mcp_servers/calendar_server/server.py
```

Isso vai abrir o navegador para autorizar. Após autorizar, o `token.json` será salvo automaticamente.

## Tools Disponíveis

### create_event
Cria evento no calendário.

```json
{
  "title": "Reunião Comercial",
  "start_datetime": "2025-11-01T14:00:00",
  "duration_minutes": 60,
  "attendee_email": "cliente@exemplo.com",
  "description": "Discussão sobre planos"
}
```

### check_availability
Verifica horários disponíveis em uma data.

```json
{
  "date": "2025-11-01",
  "start_hour": 9,
  "end_hour": 18
}
```

### list_events
Lista próximos eventos.

```json
{
  "days": 7
}
```

## Uso via MCP

```python
from mcp import ClientSession, StdioServerParameters

server = StdioServerParameters(
    command="python",
    args=["packages/mcp_servers/calendar_server/server.py"],
    env={"GOOGLE_CALENDAR_CREDENTIALS_JSON": "./secrets/google-credentials.json"}
)

async with ClientSession(server) as session:
    tools = await session.list_tools()
    result = await session.call_tool("check_availability", {"date": "2025-11-01"})
```
