# src/tasks/mom_merge_task.py
from crewai import Task

def build_mom_merge_task(mom_path: str, 
                        action_items_path: str,
                        agent,
                        output_format: str = "markdown") -> Task:
    """
    Build a task for merging reviewed action items with Minutes of Meeting.
    
    Args:
        mom_path: Path to minutes_of_meeting.md
        action_items_path: Path to reviewed_action_items.json
        agent: The MoM merger agent
        output_format: Desired output format (markdown or json)
        
    Returns:
        Configured CrewAI Task
    """
    
    description = f"""
CRITICAL INSTRUCTIONS:

1. **FIRST**: Use the MomAndActionItemsReader tool with these paths:
   - mom_path: '{mom_path}'
   - action_items_path: '{action_items_path}'

2. **ANALYZE** the tool output to understand:
   - The complete original MoM structure
   - The meeting date from the "Date and Time" section (e.g., "November 1, 2025")
   - The reviewed action items with all their fields

3. **DATE CALCULATION LOGIC** (VERY IMPORTANT):
   For each action item, handle the due_date as follows:
   
   a) If due_date is "Not specified" and due_date_calculated is null:
      - Keep as "Not specified"
   b) Consider to capture date  with resptect to meetining date for cases Today, Tomorrow, End of this week, Next week, EOD etc.
      - Example : If meeting date is "November 1, 2025" and due_date says "Today":
        * Format as: "Friday, (01-11-2025)"
      - Example : If meeting date is "November 1, 2025" and if due_date says "Tomorrow":
        * Format as: "Saturday, (02-11-2025)"
      - Example : If meeting date is "November 1, 2025" and due_date says "End of this week":
         * End of this week is Sunday, November 3, 2025
         * Format: "Sunday, (03-11-2025)"
   c) If due_date contains a day name (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday) 
      AND due_date_calculated is null:
      - Extract the meeting date from the MoM (from "Date and Time" section)
      - Calculate which date that day falls on AFTER the meeting date
      - Format as: "DayName, (DD-MM-YYYY)"
      - Example: If meeting is "November 1, 2025" (Friday) and due_date says "Monday":
        * Next Monday is November 3, 2025
        * Format: "Monday, (03-11-2025)"
      - Example: If meeting is "November 1, 2025" (Friday) and due_date says "Wednesday":
        * Next Wednesday is November 5, 2025
        * Format: "Wednesday, (05-11-2025)"
   
   d) If due_date already has a calculated date in format "Day, (DD-MM-YYYY)":
      - Use it as-is
   
   e) If due_date_calculated exists and is not null:
      - Use the format: "DayName, (due_date_calculated)"

4. **UPDATE ONLY THE ACTION ITEMS SECTION**:
   - Replace the existing Action Items section with the reviewed action items
   - Each action item MUST include ALL these fields in this EXACT format:
     
     - **[Description]** - Owner: [Name] ([Email]) - Due: [Date with calculated date] - Priority: [Priority] - Status: [Status]
   
   - Field formatting rules:
     * Description: Keep as provided, in bold with **
     * Owner: "Name (email)" format, or "Not specified" if no owner
     * Due: Use the calculated date logic above
     * Priority: Capitalize first letter only (High/Medium/Low)
     * Status: Capitalize first letter, replace underscores with spaces (Pending/In Progress/Completed/Blocked)

5. **PRESERVE ALL OTHER SECTIONS**:
   - Keep ALL other sections exactly as they are in the original MoM
   - Do NOT modify: Meeting Title, Date and Time, Team/Department, Participants, 
     Executive Summary, Key Discussion Topics, Decisions Made, Questions & Concerns, 
     Next Steps, Additional Notes
   - Maintain the exact same markdown formatting (headers, bullets, bold text, etc.)

6. **OUTPUT FORMAT**:
   - Return the complete updated MoM in markdown format
   - Start with ``` and end with ```
   - Keep the same section order as the original
   - Use ### for section headers
   - Use --- as section separators

CRITICAL: The ONLY change should be in the Action Items section. Everything else stays identical.

Example of correct action item format with calculated dates:
- **Share the agenda for today's sprint review.** - Owner: soumya paul (Soumyapaul22@gmail.com) - Due: Not specified - Priority: Medium - Status: Pending
- **Prepare the draft for review by Wednesday.** - Owner: soumya paul (Soumyapaul22@gmail.com) - Due: Wednesday, (05-11-2025) - Priority: Medium - Status: Pending
- **Complete the report by Monday.** - Owner: john doe (john@example.com) - Due: Monday, (03-11-2025) - Priority: High - Status: Pending

DO NOT add emojis, icons, or any special characters. Keep it clean and professional.
"""
    
    expected_output = (
        "A complete Minutes of Meeting markdown document with ONLY the Action Items section updated. "
        "The updated Action Items section must show all fields (description, owner with email, due date "
        "with calculated calendar date based on meeting date, priority, and status) in the specified format. "
        "All other sections must remain exactly as they were in the original document."
    )
    
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        name="MergeActionItemsWithMoM",
    )