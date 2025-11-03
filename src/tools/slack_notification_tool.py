# src/tools/slack_notification_tool.py
from crewai.tools import BaseTool
from typing import Dict, Any, Optional, List
import requests
import json
from datetime import datetime

class SlackNotificationTool(BaseTool):
    name: str = "SlackNotifier"
    description: str = (
        "Send formatted notifications to Slack channels or users. "
        "Can send updates about meeting minutes, action items, and task assignments. "
        "Supports rich formatting with blocks and attachments."
    )

    def _format_action_items(self, action_items: List[Dict], max_items: int = 5) -> str:
        """Format action items for Slack message."""
        if not action_items:
            return "_No action items_"
        
        formatted = []
        for i, item in enumerate(action_items[:max_items], 1):
            owner = item.get('owner', {})
            owner_name = owner.get('name', 'Not specified')
            due_date = item.get('due_date', 'Not specified')
            priority = item.get('priority', 'medium').title()
            status = item.get('status', 'pending').replace('_', ' ').title()
            
            # Use emoji for priority
            priority_emoji = {
                'high': '🔴',
                'medium': '🟡',
                'low': '🟢'
            }.get(priority.lower(), '⚪')
            
            # Use emoji for status
            status_emoji = {
                'pending': '⏳',
                'in_progress': '🔄',
                'completed': '✅',
                'blocked': '🚫'
            }.get(status.lower().replace(' ', '_'), '📋')
            
            item_text = (
                f"{i}. {priority_emoji} *{item.get('description', 'No description')}*\n"
                f"   👤 {owner_name} | 📅 {due_date} | {status_emoji} {status}"
            )
            formatted.append(item_text)
        
        result = "\n".join(formatted)
        
        if len(action_items) > max_items:
            result += f"\n\n_...and {len(action_items) - max_items} more items_"
        
        return result

    def _create_mom_update_blocks(self, data: Dict[str, Any]) -> List[Dict]:
        """Create Slack blocks for MoM update notification."""
        meeting_date = data.get('meeting_date', 'Unknown date')
        action_items = data.get('action_items', [])
        total_items = len(action_items)
        updated_at = data.get('updated_at', datetime.now().isoformat())
        
        # Parse datetime for better formatting
        try:
            dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            time_str = dt.strftime('%I:%M %p on %B %d, %Y')
        except:
            time_str = updated_at
        
        blocks = [
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
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Updated:*\n{time_str}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        
        # Add action items section
        if action_items:
            action_items_text = self._format_action_items(action_items)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Action Items:*\n\n{action_items_text}"
                }
            })
        
        # Add footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 _Check the updated Minutes of Meeting for full details_"
                }
            ]
        })
        
        return blocks

    def _create_simple_message(self, message: str) -> Dict[str, Any]:
        """Create a simple text message."""
        return {
            "text": message
        }

    def _send_to_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to Slack via webhook."""
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Notification sent successfully",
                    "status_code": 200
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to send notification: {response.text}",
                    "status_code": response.status_code
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"Error sending notification: {str(e)}",
                "error": str(e)
            }

    def _run(self, 
             webhook_url: str,
             data: Optional[Dict[str, Any]] = None,
             message: Optional[str] = None,
             notification_type: str = "mom_update") -> Dict[str, Any]:
        """
        Send a notification to Slack.
        
        Args:
            webhook_url: Slack webhook URL
            data: Dictionary containing meeting data (for structured notifications)
            message: Simple text message (for basic notifications)
            notification_type: Type of notification (mom_update, simple, custom)
            
        Returns:
            Dictionary with success status and message
        """
        if not webhook_url:
            return {
                "success": False,
                "message": "Webhook URL is required"
            }
        
        # Create payload based on notification type
        if notification_type == "mom_update" and data:
            blocks = self._create_mom_update_blocks(data)
            payload = {
                "blocks": blocks,
                "text": f"Meeting Minutes updated for {data.get('meeting_date', 'Unknown date')}"
            }
        elif notification_type == "simple" and message:
            payload = self._create_simple_message(message)
        elif notification_type == "custom" and data:
            # Allow custom payload
            payload = data
        else:
            return {
                "success": False,
                "message": "Invalid notification configuration. Provide either data for mom_update or message for simple notification."
            }
        
        # Send the notification
        return self._send_to_webhook(webhook_url, payload)


class SlackThreadNotificationTool(BaseTool):
    name: str = "SlackThreadNotifier"
    description: str = (
        "Send threaded replies to existing Slack messages. "
        "Useful for updates and follow-ups on action items."
    )
    
    def _run(self,
             webhook_url: str,
             message: str,
             thread_ts: str) -> Dict[str, Any]:
        """
        Send a threaded reply to Slack.
        
        Args:
            webhook_url: Slack webhook URL
            message: Message to send
            thread_ts: Thread timestamp to reply to
            
        Returns:
            Dictionary with success status
        """
        payload = {
            "text": message,
            "thread_ts": thread_ts
        }
        
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            return {
                "success": response.status_code == 200,
                "message": "Thread reply sent" if response.status_code == 200 else f"Failed: {response.text}",
                "status_code": response.status_code
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }