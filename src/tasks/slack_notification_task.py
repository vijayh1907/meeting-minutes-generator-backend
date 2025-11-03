# src/tasks/slack_notification_task.py
from crewai import Task
from typing import Optional

def build_slack_notification_task(
    webhook_url: str,
    data_source: str,
    agent,
    notification_type: str = "mom_update",
    custom_message: Optional[str] = None
) -> Task:
    """
    Build a task for sending Slack notifications about meeting updates.
    
    Args:
        webhook_url: Slack webhook URL for sending notifications
        data_source: Path to the data file (action_items.json or response JSON)
        agent: The Slack notifier agent
        notification_type: Type of notification (mom_update, simple, reminder)
        custom_message: Optional custom message for simple notifications
        
    Returns:
        Configured CrewAI Task
    """
    
    if notification_type == "mom_update":
        description = f"""
CRITICAL INSTRUCTIONS:

Your task is to send a professional Slack notification about the updated Meeting Minutes.

1. **READ THE DATA**:
   - Read the action items data from: '{data_source}'
   - This file contains the meeting date, action items, and update timestamp

2. **USE THE SLACK NOTIFICATION TOOL**:
   - Tool name: SlackNotifier
   - Pass the webhook_url: '{webhook_url}'
   - Pass the data from the JSON file
   - Set notification_type: 'mom_update'

3. **NOTIFICATION REQUIREMENTS**:
   The Slack message MUST include:
   - Clear header indicating MoM update
   - Meeting date
   - Total number of action items
   - List of action items with:
     * Priority indicators (🔴 High, 🟡 Medium, 🟢 Low)
     * Owner names
     * Due dates
     * Status indicators (⏳ Pending, 🔄 In Progress, ✅ Completed, 🚫 Blocked)
   - Timestamp of when the update was made
   - Professional and scannable formatting

4. **FORMATTING GUIDELINES**:
   - Use Slack markdown for emphasis (*bold*, _italic_)
   - Use emojis for visual clarity
   - Keep action items concise (show first 5, then "...and X more")
   - Include dividers for visual separation
   - Add a helpful footer message

5. **ERROR HANDLING**:
   - If the webhook fails, report the error clearly
   - If data is missing, still send a notification indicating an update occurred

6. **EXECUTION**:
   - Call the SlackNotifier tool with the correct parameters
   - Return a confirmation message indicating success or failure

IMPORTANT: The tool will handle all the formatting. Your job is to:
1. Read the data from the file
2. Call the tool with the correct parameters
3. Report the result

Example tool call structure:
- webhook_url: The Slack webhook URL
- data: The complete data object from the JSON file
- notification_type: 'mom_update'
"""
        
        expected_output = (
            "A confirmation message indicating whether the Slack notification was sent successfully. "
            "Include the status code and any relevant details about the notification delivery. "
            "If successful, confirm that team members have been notified of the MoM update and action items. "
            "If failed, provide clear error details."
        )
    
    elif notification_type == "simple":
        description = f"""
Send a simple text notification to Slack.

1. **USE THE SLACK NOTIFICATION TOOL**:
   - Tool: SlackNotifier
   - webhook_url: '{webhook_url}'
   - message: '{custom_message or "Meeting update notification"}'
   - notification_type: 'simple'

2. **TASK**:
   - Send the message to Slack
   - Report success or failure

Keep it simple and straightforward.
"""
        
        expected_output = (
            "Confirmation that the simple message was sent to Slack successfully."
        )
    
    elif notification_type == "reminder":
        description = f"""
Send action item reminders to Slack.

1. **READ THE DATA**:
   - Read action items from: '{data_source}'
   - Filter items that are due soon or overdue

2. **CREATE REMINDER MESSAGE**:
   - Highlight urgent items (due today or overdue)
   - Include owner names prominently
   - Use attention-grabbing emojis (⚠️, 🔔, ⏰)
   - Keep it brief but actionable

3. **SEND NOTIFICATION**:
   - Use SlackNotifier tool
   - webhook_url: '{webhook_url}'
   - Format as a reminder (not a full MoM update)

Make it clear that this is a reminder and action is needed.
"""
        
        expected_output = (
            "Confirmation that reminders were sent to the appropriate team members via Slack."
        )
    
    else:
        description = "Send a custom Slack notification."
        expected_output = "Notification sent confirmation."
    
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        name="SendSlackNotification",
    )