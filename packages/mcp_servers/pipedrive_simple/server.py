#!/usr/bin/env python3
import asyncio, logging, os, json
from typing import Dict, Any
from dotenv import load_dotenv
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('PIPEDRIVE_API_TOKEN')
DOMAIN = os.getenv('PIPEDRIVE_COMPANY_DOMAIN')
BASE_URL = f"https://{DOMAIN}.pipedrive.com/api/v1" if DOMAIN else None

class PipedriveClient:
    def __init__(self, token, base_url):
        self.token, self.base_url = token, base_url
    
    async def create_lead(self, title, person_name, person_email, person_phone="", organization_name="", note=""):
        """
        Creates a lead in Pipedrive
        Uses Pipedrive Leads API: POST /v1/leads

        Args:
            title: Lead title
            person_name: Contact name
            person_email: Contact email
            person_phone: Contact phone (WhatsApp number)
            organization_name: Organization name (optional)
            note: Note to attach to lead (optional)
        """
        async with httpx.AsyncClient() as client:
            # Step 1: Create or find person first (Leads API requires person_id)
            person_id = None
            search_term = person_email or person_phone  # Search by email first, fallback to phone

            if search_term:
                # Search for existing person by email or phone
                search_url = f"{self.base_url}/persons/search"
                search_params = {"api_token": self.token, "term": search_term}
                if person_email:
                    search_params["fields"] = "email"
                else:
                    search_params["fields"] = "phone"

                search_resp = await client.get(search_url, params=search_params)
                search_data = search_resp.json()

                if search_data.get("success") and search_data.get("data", {}).get("items"):
                    # Person exists, use their ID
                    person_id = search_data["data"]["items"][0]["item"]["id"]
                    logger.info(f"Found existing person: {person_id}")
                else:
                    # Create new person with email and phone
                    person_url = f"{self.base_url}/persons"
                    person_payload = {
                        "name": person_name or person_email or person_phone
                    }

                    # Add email if provided
                    if person_email:
                        person_payload["email"] = [person_email]

                    # Add phone if provided (WhatsApp number)
                    if person_phone:
                        person_payload["phone"] = [person_phone]

                    person_resp = await client.post(person_url, params={"api_token": self.token}, json=person_payload)
                    person_resp.raise_for_status()
                    person_id = person_resp.json()["data"]["id"]
                    logger.info(f"Created new person: {person_id} with email={person_email}, phone={person_phone}")

            # Step 2: Create lead with person_id
            lead_url = f"{self.base_url}/leads"
            lead_payload = {"title": title, "visible_to": "3"}

            if person_id:
                lead_payload["person_id"] = person_id

            logger.info(f"Creating lead with payload: {lead_payload}")
            lead_resp = await client.post(lead_url, params={"api_token": self.token}, json=lead_payload)

            # Log response for debugging
            logger.info(f"Pipedrive API Response: status={lead_resp.status_code}, body={lead_resp.text[:500]}")

            lead_resp.raise_for_status()
            lead_data = lead_resp.json()["data"]

            # Step 3: Add note if provided
            if note:
                note_url = f"{self.base_url}/notes"
                note_payload = {"content": note, "lead_id": lead_data["id"]}
                await client.post(note_url, params={"api_token": self.token}, json=note_payload)

            return {
                "lead_id": lead_data["id"],
                "title": title,
                "person_email": person_email,
                "person_id": person_id,
                "url": f"https://{DOMAIN}.pipedrive.com/leads/inbox/{lead_data['id']}"
            }

client = PipedriveClient(TOKEN, BASE_URL) if TOKEN and DOMAIN else None
app = Server("pipedrive")

@app.list_tools()
async def list_tools():
    return [Tool(
        name="create_lead",
        description="Creates lead in Pipedrive after scheduling. Phone is WhatsApp number from user_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Lead title"},
                "person_name": {"type": "string", "description": "Contact name"},
                "person_email": {"type": "string", "description": "Contact email"},
                "person_phone": {"type": "string", "description": "Contact phone (WhatsApp number from user_id)"},
                "organization_name": {"type": "string", "description": "Organization name (optional)"},
                "note": {"type": "string", "description": "Note with meeting details"}
            },
            "required": ["title", "person_name"]
        }
    )]

@app.call_tool()
async def call_tool(name, arguments):
    if not client:
        return [TextContent(type="text", text=json.dumps({"error": "Pipedrive not configured"}))]
    try:
        result = await client.create_lead(**arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

async def main():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
