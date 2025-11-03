# quick_slack_notify.py - Simple Slack notification (no imports needed)
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
import os
# Load environment variables
load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
# Configuration
WEBHOOK_URL = SLACK_WEBHOOK_URL
DATA_FILE = "outputs/action_items.json"

def main():
    print("=" * 70)
    print("QUICK SLACK NOTIFICATION")
    print("=" * 70)
    print()
    
    # Check file exists
    if not Path(DATA_FILE).exists():
        print(f"❌ ERROR: {DATA_FILE} not found")
        print("Run: python crewAgent3.py first")
        return
    
    # Load data
    print(f"Loading: {DATA_FILE}")
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    meeting_date = data.get('meeting_date', 'Unknown')
    total_items = data.get('total_items', 0)
    action_items = data.get('action_items', [])
    
    print(f"  Meeting: {meeting_date}")
    print(f"  Items: {total_items}")
    print()
    
    # Format items
    items = []
    for i, item in enumerate(action_items[:5], 1):
        owner = item.get('owner', {}).get('name', 'Not specified')
        desc = item.get('description', 'No description')
        due = item.get('due_date', 'Not specified')
        priority = item.get('priority', 'medium')
        
        # Priority emoji
        emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '⚪')
        
        items.append(f"{i}. {emoji} *{desc}*\n   👤 {owner} | 📅 {due}")
    
    items_text = "\n".join(items)
    if total_items > 5:
        items_text += f"\n\n_...and {total_items - 5} more items_"
    
    # Build Slack message
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📋 Meeting Minutes Updated",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Meeting Date:*\n{meeting_date}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Action Items:*\n{total_items}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Action Items:*\n\n{items_text}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 _Check the updated Minutes of Meeting for full details_"
                    }
                ]
            }
        ],
        "text": f"Meeting Minutes updated for {meeting_date}"
    }
    
    # Send to Slack
    print("📤 Sending to Slack...")
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ SUCCESS! Notification sent to Slack!")
            print()
            print("🎉 Check your Slack channel for the message!")
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(f"Response: {response.text}")
            print()
            print("Check your webhook URL is correct.")
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print()
        print("Make sure you have internet connection and webhook is valid.")

if __name__ == "__main__":
    main()