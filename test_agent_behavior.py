#!/usr/bin/env python3
"""
Test Agent Behavior with Conversation History
Simulates a real booking flow with context preservation
"""
import requests
import json

API_URL = "http://localhost:8000/api/chat"

def chat(user_id: str, message: str, previous_messages=None, context=None):
    """Send chat request to API"""
    
    payload = {
        "user_id": user_id,
        "message": message
    }
    
    # Add context with history if provided
    if previous_messages or context:
        payload["context"] = {
            "previous_messages": previous_messages or [],
            **(context or {})
        }
    
    response = requests.post(API_URL, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"ERROR: {response.status_code} - {response.text}")
        return None


def main():
    """Test conversation flow"""
    
    print("\n" + "="*80)
    print("AGENT BEHAVIOR TEST - Conversation History")
    print("="*80 + "\n")
    
    user_id = "test_user_123"
    conversation = []
    
    # Message 1: Check availability
    print("USER: Hoje tem horário?")
    result = chat(user_id, "Hoje tem horário?")
    
    if result:
        agent_response = result["response"]
        print(f"AGENT: {agent_response}\n")
        
        # Add to history
        conversation.append({"role": "user", "content": "Hoje tem horário?"})
        conversation.append({"role": "assistant", "content": agent_response})
    
    # Message 2: Choose time (WITH HISTORY)
    print("USER: As 11")
    result = chat(
        user_id,
        "As 11",
        previous_messages=conversation
    )
    
    if result:
        agent_response = result["response"]
        print(f"AGENT: {agent_response}\n")
        
        # Add to history
        conversation.append({"role": "user", "content": "As 11"})
        conversation.append({"role": "assistant", "content": agent_response})
    
    # Message 3: Provide email (WITH HISTORY)
    print("USER: financeiro@alabia.com.br")
    result = chat(
        user_id,
        "financeiro@alabia.com.br",
        previous_messages=conversation
    )
    
    if result:
        agent_response = result["response"]
        print(f"AGENT: {agent_response}\n")
        
        print("="*80)
        print("EXPECTED BEHAVIOR:")
        print("  - Agent should remember the 11h appointment")
        print("  - Agent should create the event with the email provided")
        print("  - Agent should NOT ask 'How can I help?'")
        print("="*80 + "\n")
        
        # Check if create_event was called
        if result.get("actions"):
            print("TOOLS CALLED:")
            for action in result["actions"]:
                print(f"  - {action['tool']}: {action['status']}")
        else:
            print("⚠️  WARNING: No tools were called!")
    
    print("\nCONVERSATION HISTORY:")
    print(json.dumps(conversation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
