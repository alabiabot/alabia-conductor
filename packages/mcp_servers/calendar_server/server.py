#!/usr/bin/env python3
"""
Google Calendar MCP Server
Expõe ferramentas para agendamento via Model Context Protocol
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from pathlib import Path

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: MCP not installed. Run: pip install mcp")
    exit(1)

# Google Calendar imports
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("ERROR: Google Client not installed. Run: pip install google-auth google-api-python-client")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scopes do Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Server MCP
server = Server("alabia-calendar-server")


class CalendarClient:
    """Cliente para Google Calendar API"""

    def __init__(self, credentials_path: str):
        """
        Inicializa cliente do Calendar

        Args:
            credentials_path: Caminho para credentials.json
        """
        self.credentials_path = credentials_path
        self.creds = None
        self.service = None

    def authenticate(self):
        """Autentica com Google Calendar"""
        token_path = Path(self.credentials_path).parent / "token.json"

        # Carrega token salvo
        if token_path.exists():
            self.creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        # Se não tem credenciais válidas, faz login
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                # Tenta usar run_local_server, mas se falhar (WSL), usa run_console
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                try:
                    # Tenta abrir navegador (funciona no Windows/Mac/Linux com GUI)
                    self.creds = flow.run_local_server(port=0, open_browser=False)
                except Exception as e:
                    logger.warning(f"run_local_server failed (WSL?): {e}")
                    logger.info("Switching to console flow...")
                    # Fallback para console flow (mostra URL para copiar)
                    self.creds = flow.run_console()

            # Salva token para próximas execuções
            with open(token_path, 'w') as token:
                token.write(self.creds.to_json())

        self.service = build('calendar', 'v3', credentials=self.creds)
        logger.info("Authenticated with Google Calendar")

    def create_event(
        self,
        title: str,
        start_datetime: str,
        duration_minutes: int = 60,
        attendee_email: str = None,
        description: str = None,
        calendar_id: str = 'primary'
    ) -> Dict[str, Any]:
        """
        Cria evento no calendário

        Args:
            title: Título do evento
            start_datetime: Data/hora início (ISO 8601)
            duration_minutes: Duração em minutos
            attendee_email: Email do participante
            description: Descrição do evento
            calendar_id: ID do calendário

        Returns:
            Informações do evento criado
        """
        try:
            # Parse datetime
            start = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
            end = start + timedelta(minutes=duration_minutes)

            event = {
                'summary': title,
                'description': description or f"Reunião agendada via Alabia Conductor",
                'start': {
                    'dateTime': start.isoformat(),
                    'timeZone': 'America/Sao_Paulo',
                },
                'end': {
                    'dateTime': end.isoformat(),
                    'timeZone': 'America/Sao_Paulo',
                },
                # Adiciona Google Meet automaticamente
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"alabia-{start.timestamp()}",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
            }

            if attendee_email:
                event['attendees'] = [{'email': attendee_email}]
                event['sendUpdates'] = 'all'  # Envia email para participantes

            # Cria evento com Google Meet
            # conferenceDataVersion=1 é necessário para criar Meet
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event,
                conferenceDataVersion=1  # ✅ Necessário para Google Meet
            ).execute()

            logger.info(f"Event created: {created_event.get('id')}")

            # Extrai link do Google Meet
            meet_link = None
            if 'conferenceData' in created_event:
                entry_points = created_event['conferenceData'].get('entryPoints', [])
                for entry in entry_points:
                    if entry.get('entryPointType') == 'video':
                        meet_link = entry.get('uri')
                        break

            return {
                "event_id": created_event.get('id'),
                "title": created_event.get('summary'),
                "start": created_event['start'].get('dateTime'),
                "end": created_event['end'].get('dateTime'),
                "status": created_event.get('status'),
                "calendar_link": created_event.get('htmlLink'),
                "meet_link": meet_link,  # ✅ Link do Google Meet
                "attendee_email": attendee_email
            }

        except HttpError as error:
            logger.error(f"Error creating event: {error}")
            raise Exception(f"Failed to create event: {error}")

    def check_availability(
        self,
        date: str,
        start_hour: int = 9,
        end_hour: int = 18,
        calendar_id: str = 'primary'
    ) -> Dict[str, Any]:
        """
        Verifica slots disponíveis em uma data

        Args:
            date: Data para verificar (YYYY-MM-DD)
            start_hour: Hora início do expediente
            end_hour: Hora fim do expediente
            calendar_id: ID do calendário

        Returns:
            Slots disponíveis
        """
        try:
            # Parse date
            target_date = datetime.fromisoformat(date)
            time_min = target_date.replace(hour=start_hour, minute=0, second=0)
            time_max = target_date.replace(hour=end_hour, minute=0, second=0)

            # Lista eventos do dia
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Calcula slots disponíveis (simplificado: hora cheia)
            busy_hours = set()
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                if start:
                    hour = datetime.fromisoformat(start.replace('Z', '+00:00')).hour
                    busy_hours.add(hour)

            available_slots = [
                f"{hour:02d}:00"
                for hour in range(start_hour, end_hour)
                if hour not in busy_hours
            ]

            return {
                "date": date,
                "available_slots": available_slots,
                "busy_hours": list(busy_hours)
            }

        except HttpError as error:
            logger.error(f"Error checking availability: {error}")
            raise Exception(f"Failed to check availability: {error}")

    def list_events(
        self,
        days: int = 7,
        calendar_id: str = 'primary'
    ) -> Dict[str, Any]:
        """
        Lista próximos eventos

        Args:
            days: Número de dias para frente
            calendar_id: ID do calendário

        Returns:
            Lista de eventos
        """
        try:
            now = datetime.now()
            time_max = now + timedelta(days=days)

            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=now.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            return {
                "count": len(events),
                "events": [
                    {
                        "id": event['id'],
                        "title": event.get('summary', 'No title'),
                        "start": event['start'].get('dateTime', event['start'].get('date')),
                        "end": event['end'].get('dateTime', event['end'].get('date')),
                    }
                    for event in events
                ]
            }

        except HttpError as error:
            logger.error(f"Error listing events: {error}")
            raise Exception(f"Failed to list events: {error}")

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
        try:
            # Opção 1: Deletar completamente o evento
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all' if send_updates else 'none'
            ).execute()

            logger.info(f"Event deleted: {event_id}")

            return {
                "event_id": event_id,
                "status": "cancelled",
                "message": "Evento cancelado com sucesso"
            }

        except HttpError as error:
            logger.error(f"Error cancelling event: {error}")
            raise Exception(f"Failed to cancel event: {error}")


# Cliente global
calendar_client = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Lista tools disponíveis"""
    return [
        Tool(
            name="create_event",
            description="Cria um evento no Google Calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Título do evento/reunião"
                    },
                    "start_datetime": {
                        "type": "string",
                        "description": "Data e hora de início no formato ISO 8601 (ex: 2025-11-01T14:00:00)"
                    },
                    "duration_minutes": {
                        "type": "number",
                        "description": "Duração em minutos (padrão: 60)"
                    },
                    "attendee_email": {
                        "type": "string",
                        "description": "Email do participante"
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição adicional da reunião"
                    }
                },
                "required": ["title", "start_datetime"]
            }
        ),
        Tool(
            name="check_availability",
            description="Verifica horários disponíveis no calendário para uma data específica",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Data para verificar no formato YYYY-MM-DD"
                    },
                    "start_hour": {
                        "type": "number",
                        "description": "Hora de início do expediente (padrão: 9)"
                    },
                    "end_hour": {
                        "type": "number",
                        "description": "Hora de fim do expediente (padrão: 18)"
                    }
                },
                "required": ["date"]
            }
        ),
        Tool(
            name="list_events",
            description="Lista próximos eventos do calendário",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "number",
                        "description": "Número de dias para frente (padrão: 7)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="cancel_event",
            description="Cancela/deleta um evento do calendário. Use quando o cliente quiser reagendar ou cancelar uma reunião.",
            inputSchema={
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
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Executa tool"""
    import json
    global calendar_client

    if not calendar_client:
        error_result = {"error": "Calendar client not initialized", "tool": name}
        return [TextContent(type="text", text=json.dumps(error_result, ensure_ascii=False))]

    try:
        if name == "create_event":
            result = calendar_client.create_event(**arguments)
        elif name == "check_availability":
            result = calendar_client.check_availability(**arguments)
        elif name == "list_events":
            result = calendar_client.list_events(**arguments)
        elif name == "cancel_event":
            result = calendar_client.cancel_event(**arguments)
        else:
            error_result = {"error": f"Unknown tool: {name}", "tool": name}
            return [TextContent(type="text", text=json.dumps(error_result, ensure_ascii=False))]

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        logger.error(f"Error executing {name}: {e}", exc_info=True)
        # Return error as JSON
        error_result = {
            "error": str(e),
            "tool": name,
            "arguments": arguments
        }
        return [TextContent(type="text", text=json.dumps(error_result, ensure_ascii=False))]


async def main():
    """Main entry point"""
    global calendar_client

    # Inicializa cliente do Calendar
    import os
    credentials_path = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", "./secrets/google-credentials.json")

    logger.info(f"Initializing Calendar Server with credentials: {credentials_path}")

    calendar_client = CalendarClient(credentials_path)
    calendar_client.authenticate()

    logger.info("Calendar MCP Server ready")

    # Roda servidor MCP via stdio
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
