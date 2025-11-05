# 🎥 Google Meet Integration

## Overview

Todos os eventos criados pelo Alabia Conductor agora incluem **automaticamente** um link do Google Meet, tornando os agendamentos completos e profissionais sem necessidade de configuração adicional.

**Status:** ✅ **IMPLEMENTADO**

---

## O Que Foi Adicionado

### 1. Criação Automática de Google Meet

Quando o agent cria um evento via `create_event`, o Google Calendar API automaticamente:
- ✅ Cria um link único do Google Meet
- ✅ Adiciona o link ao convite por email
- ✅ Retorna o link para o agent mostrar ao cliente

**Arquivo:** `packages/mcp_servers/calendar_server/server.py`

### 2. Retorno do Meet Link

O `create_event` agora retorna:

```json
{
  "event_id": "abc123xyz",
  "title": "Reunião Comercial - Alabia",
  "start": "2025-11-04T14:00:00",
  "end": "2025-11-04T15:00:00",
  "status": "confirmed",
  "calendar_link": "https://calendar.google.com/event?eid=...",
  "meet_link": "https://meet.google.com/xyz-abcd-efg",  // ✅ NOVO!
  "attendee_email": "cliente@email.com"
}
```

### 3. Agent Sempre Menciona o Link

O prompt foi atualizado para instruir o agent a **sempre** mostrar o link do Meet ao confirmar agendamento.

**Arquivo:** `packages/llm/prompts.py`

---

## Como Funciona

### Implementação Técnica

**Antes (sem Meet):**
```python
event = {
    'summary': title,
    'start': {...},
    'end': {...}
}

created_event = service.events().insert(
    calendarId='primary',
    body=event
).execute()
```

**Depois (com Meet):**
```python
event = {
    'summary': title,
    'start': {...},
    'end': {...},
    # ✅ Configuração do Google Meet
    'conferenceData': {
        'createRequest': {
            'requestId': f"alabia-{start.timestamp()}",
            'conferenceSolutionKey': {'type': 'hangoutsMeet'}
        }
    }
}

created_event = service.events().insert(
    calendarId='primary',
    body=event,
    conferenceDataVersion=1  # ✅ Necessário para criar Meet!
).execute()

# Extrai link do Meet
meet_link = None
if 'conferenceData' in created_event:
    for entry in created_event['conferenceData'].get('entryPoints', []):
        if entry.get('entryPointType') == 'video':
            meet_link = entry.get('uri')
```

---

## Exemplo de Uso

### Fluxo do Usuário:

```
User: "Quero agendar para amanhã 14h"
Agent: [calls check_availability] "14h está livre! Qual seu email?"

User: "contato@empresa.com"
Agent: [calls create_event]
Agent: "✅ Agendado para amanhã 14h!

       📧 Convite enviado para contato@empresa.com
       🎥 Link do Meet: https://meet.google.com/abc-defg-hij
       
       Até lá!"
```

### O Que o Cliente Recebe:

1. **Email do Google Calendar** com:
   - Título: "Reunião Comercial - Alabia"
   - Data e hora
   - Link do Google Meet clicável
   - Botão "Adicionar ao calendário"

2. **Mensagem do Agent** com:
   - Confirmação do agendamento
   - Email para onde foi enviado o convite
   - Link direto do Google Meet

---

## Benefícios

### Para o Cliente:
- ✅ Não precisa criar link do Meet manualmente
- ✅ Tudo pronto em uma única interação
- ✅ Link já incluído no convite por email
- ✅ Um clique para entrar na reunião

### Para a Alabia:
- ✅ Processo profissional e automatizado
- ✅ Menos fricção no agendamento
- ✅ Cliente recebe experiência completa
- ✅ Diferencial competitivo

---

## Configuração

### Não Requer Configuração Adicional!

Se o Google Calendar API está configurado (OAuth + credentials), o Google Meet funciona automaticamente.

**Requisitos:**
- ✅ Google Calendar API habilitada (já configurado)
- ✅ OAuth 2.0 credentials (já configurado)
- ✅ Escopo `https://www.googleapis.com/auth/calendar` (já configurado)

**Sem necessidade de:**
- ❌ Google Meet API separada
- ❌ Configuração adicional
- ❌ Pagamento extra (incluído no Google Workspace)

---

## Detalhes Técnicos

### conferenceData

O Google Calendar API usa `conferenceData` para criar conferências:

```python
'conferenceData': {
    'createRequest': {
        'requestId': "unique-id",  # ID único para idempotência
        'conferenceSolutionKey': {
            'type': 'hangoutsMeet'  # Tipo: Google Meet
        }
    }
}
```

**Tipos Disponíveis:**
- `hangoutsMeet` - Google Meet (padrão)
- `eventHangout` - Google Hangouts (deprecated)
- `eventNamedHangout` - Named Hangouts (deprecated)

### conferenceDataVersion

**Essencial!** Sem `conferenceDataVersion=1`, o Meet não é criado:

```python
service.events().insert(
    calendarId='primary',
    body=event,
    conferenceDataVersion=1  # ✅ Obrigatório!
).execute()
```

### Extração do Link

O link do Meet vem em `conferenceData.entryPoints`:

```python
for entry in event['conferenceData'].get('entryPoints', []):
    if entry.get('entryPointType') == 'video':
        meet_link = entry.get('uri')
        # Exemplo: https://meet.google.com/abc-defg-hij
```

**Outros Entry Points:**
- `phone` - Telefone para discagem
- `sip` - SIP para sistemas de conferência
- `more` - Mais opções

---

## Testes

### Teste Manual

```bash
# 1. Inicie o servidor
uvicorn apps.orchestrator.main:app --reload

# 2. Crie um agendamento
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "Quero agendar para amanhã 14h",
    "context": {
      "email": "seu-email@gmail.com"
    }
  }'
```

**Verificações:**
1. ✅ Agent pergunta qual email (ou usa do context)
2. ✅ Agent cria o evento
3. ✅ Resposta inclui link do Meet
4. ✅ Email recebido com link do Meet
5. ✅ Link funciona ao clicar

### Teste via Google Calendar

1. Acesse https://calendar.google.com
2. Encontre o evento criado
3. Clique no evento
4. Verifique que tem:
   - ✅ Link "Participar com o Google Meet"
   - ✅ Botão azul clicável
   - ✅ Link funciona

---

## Troubleshooting

### Meet Link Não Foi Criado

**Sintoma:** `meet_link` retorna `null`

**Causas Possíveis:**
1. `conferenceDataVersion=1` não foi passado
2. Conta Google não tem permissão para criar Meet
3. Google Workspace tem Meet desabilitado

**Solução:**
```python
# Verificar se conferenceDataVersion está presente
created_event = service.events().insert(
    calendarId='primary',
    body=event,
    conferenceDataVersion=1  # ✅ Adicione isso!
).execute()
```

### Meet Link Inválido

**Sintoma:** Link retornado mas não funciona

**Causa:** Entry point incorreto extraído

**Solução:**
```python
# Garantir que está pegando o entry point correto
for entry in entry_points:
    if entry.get('entryPointType') == 'video':  # ✅ Deve ser 'video'
        meet_link = entry.get('uri')
```

### Email Não Recebe Link

**Sintoma:** Email chega mas sem link do Meet

**Causa:** `sendUpdates` não configurado

**Solução:**
```python
event['sendUpdates'] = 'all'  # ✅ Envia para todos participantes
```

---

## Arquivos Modificados

### 1. `packages/mcp_servers/calendar_server/server.py`

**Linhas 128-134:** Adiciona conferenceData
```python
'conferenceData': {
    'createRequest': {
        'requestId': f"alabia-{start.timestamp()}",
        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
    }
}
```

**Linha 146:** Adiciona conferenceDataVersion
```python
conferenceDataVersion=1
```

**Linhas 151-158:** Extrai Meet link
```python
meet_link = None
if 'conferenceData' in created_event:
    for entry in created_event['conferenceData'].get('entryPoints', []):
        if entry.get('entryPointType') == 'video':
            meet_link = entry.get('uri')
```

**Linha 167:** Retorna Meet link
```python
"meet_link": meet_link
```

### 2. `packages/llm/prompts.py`

**Linhas 81-84:** Instrução sobre Meet
```python
**⭐ IMPORTANTE:** O create_event SEMPRE cria um link do Google Meet automaticamente!
- Quando confirmar o agendamento, SEMPRE mencione o link do Meet
- Exemplo: "✅ Agendado! Link da reunião: [meet_link]"
```

**Linhas 113-118:** Exemplo de fluxo com Meet
```python
Você: "✅ Agendado para hoje 14h!

📧 Convite enviado para paulo@email.com
🎥 Link do Meet: [meet_link do resultado]

Até lá!"
```

---

## Próximos Passos (Opcional)

### Melhorias Futuras:

1. **Configuração Customizada:**
   - Permitir desabilitar Meet em certos tipos de reunião
   - Suporte para outras plataformas (Zoom, Teams)

2. **Notificações:**
   - Lembrete 10 minutos antes com link do Meet
   - SMS com link do Meet

3. **Analytics:**
   - Rastrear quantas pessoas clicam no link
   - Taxa de comparecimento em reuniões

4. **Integração Zoom:**
   - Opção de criar Zoom ao invés de Meet
   - Configurável por cliente

---

## Referências

- [Google Calendar API - Conference Data](https://developers.google.com/calendar/api/v3/reference/events#conferenceData)
- [Creating Events with Google Meet](https://developers.google.com/calendar/api/guides/create-events#conference-data)
- [Google Meet Developer Guide](https://developers.google.com/meet)

---

**Status:** ✅ **IMPLEMENTADO E FUNCIONANDO**
**Data:** 02/Nov/2025
**Versão:** 1.0
