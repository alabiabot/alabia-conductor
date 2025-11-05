#!/usr/bin/env python3
"""
Test Calendar MCP Server Integration
Tests the Calendar server connection and tools via MCP orchestrator
"""
import asyncio
import logging
from datetime import datetime, timedelta
from apps.orchestrator.mcp_client import MCPOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_calendar_integration():
    """Test Calendar server integration"""

    print("\n" + "="*80)
    print("CALENDAR MCP SERVER - INTEGRATION TEST")
    print("="*80 + "\n")

    # Initialize orchestrator
    orchestrator = MCPOrchestrator()

    try:
        print("1. Initializing MCP Orchestrator...")
        await orchestrator.initialize()
        print(f"    Initialized with {len(orchestrator.tools)} tools\n")

        # List all tools
        print("2. Available Tools:")
        for tool_name, tool_info in orchestrator.tools.items():
            server = orchestrator.server_for_tool.get(tool_name, "unknown")
            print(f"   - {tool_name} (from {server})")
            print(f"     {tool_info.get('description', 'No description')}")
        print()

        # Test 1: Check Availability
        print("="*80)
        print("TEST 1: check_availability")
        print("="*80)

        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"\nChecking availability for: {today}")

        try:
            result = await orchestrator.execute_tool(
                "check_availability",
                {"date": today}
            )

            print("\n Result:")
            print(f"  Date: {result.get('date')}")
            print(f"  Available slots: {result.get('available_slots')}")
            print(f"  Busy hours: {result.get('busy_hours')}")

        except Exception as e:
            print(f"\n Error: {e}")

        # Test 2: List Events
        print("\n" + "="*80)
        print("TEST 2: list_events")
        print("="*80)

        print("\nListing events for next 7 days...")

        try:
            result = await orchestrator.execute_tool(
                "list_events",
                {"days": 7}
            )

            print("\n Result:")
            print(f"  Total events: {result.get('count', 0)}")

            if result.get('events'):
                print("\n  Events:")
                for event in result['events'][:5]:  # Show first 5
                    print(f"    - {event['title']}")
                    print(f"      Start: {event['start']}")
            else:
                print("  No events found")

        except Exception as e:
            print(f"\n Error: {e}")

        # Test 3: Create Event (commented out to avoid creating test events)
        print("\n" + "="*80)
        print("TEST 3: create_event (SKIPPED)")
        print("="*80)
        print("\nTo test event creation, uncomment the code below and provide valid data:")
        print("""
        # tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0)
        # result = await orchestrator.execute_tool(
        #     "create_event",
        #     {
        #         "title": "Test Event - Alabia Conductor",
        #         "start_datetime": tomorrow.isoformat(),
        #         "duration_minutes": 60,
        #         "attendee_email": "test@example.com",
        #         "description": "Test event created by integration test"
        #     }
        # )
        # print(f"\\n Event created: {result.get('event_id')}")
        # print(f"  Link: {result.get('calendar_link')}")
        """)

        print("\n" + "="*80)
        print("TESTS COMPLETE")
        print("="*80 + "\n")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n Test failed: {e}\n")

    finally:
        print("Shutting down MCP orchestrator...")
        await orchestrator.shutdown()
        print(" Shutdown complete\n")


async def main():
    """Main entry point"""
    await test_calendar_integration()


if __name__ == "__main__":
    asyncio.run(main())
