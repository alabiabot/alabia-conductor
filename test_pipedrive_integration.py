#!/usr/bin/env python3
"""
Test Pipedrive Integration
Verifies complete flow: schedule meeting → create lead
"""
import asyncio
import logging
from apps.orchestrator.mcp_client import mcp_orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_pipedrive_integration():
    """Test Pipedrive MCP server integration"""

    print("\n" + "="*60)
    print("TESTING PIPEDRIVE INTEGRATION")
    print("="*60 + "\n")

    try:
        # 1. Initialize MCP orchestrator
        print("1. Initializing MCP orchestrator...")
        await mcp_orchestrator.initialize()
        print(f"   ✅ Initialized with {len(mcp_orchestrator.tools)} tools\n")

        # 2. Verify create_lead tool is available
        print("2. Checking if create_lead tool is registered...")
        tools = await mcp_orchestrator.get_tools()
        tool_names = [t['name'] for t in tools]
        print(f"   Available tools: {tool_names}")

        if 'create_lead' in tool_names:
            print("   ✅ create_lead tool found!\n")
        else:
            print("   ❌ create_lead tool NOT found!")
            print("   Stopping test.\n")
            return

        # 3. Test create_lead execution
        print("3. Testing create_lead tool execution...")
        test_lead_data = {
            "title": "Teste - Reunião Alabia",
            "person_name": "Paulo Teixeira (Teste)",
            "person_email": "paulo.teste@alabia.com.br",
            "person_phone": "5511947163792",  # WhatsApp number
            "organization_name": "Alabia Test",
            "note": "Lead de teste criado via MCP integration test. Reunião agendada para teste do sistema."
        }

        print(f"   Input: {test_lead_data}")
        result = await mcp_orchestrator.execute_tool('create_lead', test_lead_data)

        print(f"\n   Result: {result}\n")

        # 4. Verify result
        if isinstance(result, dict) and "error" in result:
            print(f"   ❌ Error creating lead: {result['error']}")
            if "not configured" in result.get('error', '').lower():
                print("\n   💡 Make sure PIPEDRIVE_API_TOKEN and PIPEDRIVE_COMPANY_DOMAIN are in .env")
        elif isinstance(result, dict) and "lead_id" in result:
            print(f"   ✅ Lead created successfully!")
            print(f"   📋 Lead ID: {result['lead_id']}")
            print(f"   🔗 URL: {result.get('url', 'N/A')}")
            print(f"   📧 Email: {result.get('person_email', 'N/A')}")
        else:
            print(f"   ⚠️  Unexpected result format: {result}")

        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60 + "\n")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}\n")

    finally:
        # Cleanup
        print("Cleaning up...")
        await mcp_orchestrator.shutdown()
        print("✅ Cleanup complete\n")


if __name__ == "__main__":
    asyncio.run(test_pipedrive_integration())
