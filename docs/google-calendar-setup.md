# =Å Google Calendar MCP Server - Setup Guide

## Overview

O Calendar MCP Server permite que o assistente Alabia gerencie agendamentos via Google Calendar, incluindo:
-  Verificar disponibilidade de horários
-  Criar eventos e enviar convites
-  Listar próximos compromissos

## =' Configuração

### 1. Criar Projeto no Google Cloud Console

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto ou selecione um existente
3. Ative a **Google Calendar API**:
   - Menu > APIs & Services > Library
   - Busque "Google Calendar API"
   - Clique em "Enable"

### 2. Criar Credenciais OAuth 2.0

Para **Aplicação Desktop** (desenvolvimento local):

1. No Google Cloud Console:
   - APIs & Services > Credentials
   - Create Credentials > OAuth client ID
   - Application type: **Desktop app**
   - Name: "Alabia Conductor Local"
   - Create

2. Baixe o arquivo JSON das credenciais

3. Salve o arquivo como:
   ```
   /home/pteixeira/projetos/alabia-conductor/secrets/google-credentials.json
   ```

### 3. Configurar .env

Adicione ao seu arquivo `.env`:

```bash
# Google Calendar Configuration
GOOGLE_CALENDAR_CREDENTIALS_JSON=./secrets/google-credentials.json
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIMEZONE=America/Sao_Paulo
```

**Notas:**
- `GOOGLE_CALENDAR_ID=primary` usa o calendário principal da conta
- Para usar calendário específico, use o email (ex: `comercial@alabia.com`)

### 4. Primeira Autenticação

Na primeira execução, o servidor Calendar abrirá um navegador para autenticação:

```bash
# Teste standalone do Calendar server
cd /home/pteixeira/projetos/alabia-conductor
source venv/bin/activate
python packages/mcp_servers/calendar_server/server.py
```

O fluxo será:
1. Abrirá navegador automaticamente
2. Faça login com conta Google
3. Autorize o acesso ao Google Calendar
4. Token será salvo em `secrets/token.json`

**  IMPORTANTE:** O token é salvo localmente e reutilizado nas próximas execuções.

---

## =à Tools Disponíveis

### 1. `check_availability`

Verifica horários disponíveis em uma data específica.

**Parâmetros:**
```json
{
  "date": "2025-11-02",        // YYYY-MM-DD (required)
  "start_hour": 9,              // Hora início (default: 9)
  "end_hour": 18                // Hora fim (default: 18)
}
```

**Retorno:**
```json
{
  "date": "2025-11-02",
  "available_slots": ["09:00", "11:00", "14:00", "16:00"],
  "busy_hours": [10, 12, 13, 15, 17]
}
```

**Uso no Prompt:**
```
Cliente: "Hoje tem horário?"
Agente: [CHAMA check_availability("2025-11-02")]
Agente: "Hoje temos: 9h, 11h, 14h e 16h. Qual prefere?"
```

---

### 2. `create_event`

Cria um evento no calendário e envia convite por email.

**Parâmetros:**
```json
{
  "title": "Reunião Alabia",                    // required
  "start_datetime": "2025-11-02T14:00:00",     // ISO 8601 (required)
  "duration_minutes": 60,                       // default: 60
  "attendee_email": "cliente@email.com",       // optional
  "description": "Conversa inicial sobre IA"   // optional
}
```

**Retorno:**
```json
{
  "event_id": "abc123xyz",
  "title": "Reunião Alabia",
  "start": "2025-11-02T14:00:00",
  "end": "2025-11-02T15:00:00",
  "status": "confirmed",
  "calendar_link": "https://calendar.google.com/event?eid=..."
}
```

**Uso no Prompt:**
```
Cliente: "paulo@email.com"
Agente: [CHAMA create_event({
  "title": "Reunião Alabia - Conversa Inicial",
  "start_datetime": "2025-11-02T14:00:00",
  "attendee_email": "paulo@email.com"
})]
Agente: " Agendado! Hoje às 14h. Convite enviado para paulo@email.com"
```

---

### 3. `list_events`

Lista próximos eventos do calendário.

**Parâmetros:**
```json
{
  "days": 7  // Dias à frente (default: 7)
}
```

**Retorno:**
```json
{
  "count": 3,
  "events": [
    {
      "id": "abc123",
      "title": "Reunião Cliente X",
      "start": "2025-11-02T10:00:00",
      "end": "2025-11-02T11:00:00"
    }
  ],
  "days": 7
}
```

---

## =€ Como Testar

### Teste 1: Verificar Disponibilidade

```bash
# Via API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "Hoje tem horário disponível?"
  }'
```

**Comportamento esperado:**
- Agente chama `check_availability` automaticamente
- Retorna horários disponíveis reais do calendário

### Teste 2: Criar Evento

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "Quero agendar para hoje 14h. Meu email é teste@email.com"
  }'
```

**Comportamento esperado:**
- Agente chama `create_event` com os parâmetros corretos
- Evento é criado no Google Calendar
- Convite enviado para teste@email.com

---

## = Segurança

### Arquivos Sensíveis

Adicione ao `.gitignore`:
```
secrets/
*.json
token.json
```

### Service Account (Produção)

Para produção, recomenda-se usar Service Account ao invés de OAuth:

1. No Google Cloud Console:
   - APIs & Services > Credentials
   - Create Credentials > Service Account
   - Baixe o JSON da service account

2. Compartilhe o calendário com o email da service account:
   - Acesse Google Calendar
   - Settings > Share with specific people
   - Adicione o email da service account
   - Permissão: "Make changes to events"

3. Atualize o código do Calendar server para usar service account:
   ```python
   from google.oauth2 import service_account

   credentials = service_account.Credentials.from_service_account_file(
       SERVICE_ACCOUNT_FILE,
       scopes=SCOPES
   )
   ```

---

## =Ê Monitoramento

### Health Check

```bash
curl http://localhost:8000/api/chat/health
```

Verifica:
- Status do MCP orchestrator
- Número de tools registradas
- Status de cada servidor (RAG, Calendar)

### Logs

O Calendar server loga todas as operações:
```
INFO: Connecting to Calendar server...
INFO: Authenticated with Google Calendar
INFO: Registered tool: check_availability from calendar
INFO: Registered tool: create_event from calendar
INFO: Registered tool: list_events from calendar
INFO: Calendar server connected successfully with 3 tools
```

---

## = Troubleshooting

### Erro: "GOOGLE_CALENDAR_CREDENTIALS_JSON not set"

**Solução:** Verifique se o `.env` está configurado e se o arquivo existe:
```bash
ls -la secrets/google-credentials.json
```

### Erro: "Failed to authenticate"

**Solução:** Delete o token e refaça autenticação:
```bash
rm secrets/token.json
python packages/mcp_servers/calendar_server/server.py
```

### Erro: "Calendar API not enabled"

**Solução:** Ative a API no Google Cloud Console:
- APIs & Services > Library > "Google Calendar API" > Enable

### Erro: "Insufficient Permission"

**Solução:** Verifique os escopos no OAuth consent screen:
- Deve incluir: `https://www.googleapis.com/auth/calendar`

---

## =Ú Referências

- [Google Calendar API - Python Quickstart](https://developers.google.com/calendar/api/quickstart/python)
- [Google Calendar API Reference](https://developers.google.com/calendar/api/v3/reference)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io)

---

**Versão:** 1.0
**Data:** Novembro 2025
**Autor:** Claude Code
