# src/tasks/mom_generation_task.py
from crewai import Task

def build_mom_generation_task(transcript_path: str, agent, output_format: str = "markdown") -> Task:
    """
    Build a task for generating Minutes of Meeting from reviewed transcripts.
    
    Args:
        transcript_path: Path to reviewed_transcripts.json
        agent: The MoM generator agent
        output_format: Desired output format (markdown or json)
        
    Returns:
        Configured CrewAI Task
    """
    
    if output_format == "markdown":
        description = f"""
CRITICAL: You MUST use the ReviewedTranscriptReader tool on '{transcript_path}' FIRST before writing anything.

STRICT REQUIREMENTS:
1. ONLY use information from the tool output - DO NOT invent or assume any details
2. If the tool returns meeting metadata (title, date, time, team, participants), use EXACTLY that information
3. ONLY include topics, discussions, and action items that are ACTUALLY present in the transcript
4. If information is missing from the transcript, state "Not specified" rather than inventing details
5. DO NOT add fictional names, dates, or content that doesn't exist in the source data

After calling the tool and receiving the structured data, generate a comprehensive, professional 
Minutes of Meeting (MoM) document in Markdown format using ONLY the actual data provided.

The MoM should include:

1. **Meeting Header**
   - Meeting title
   - Date and time
   - Team/Department
   - Participants/Attendees

2. **Executive Summary** (2-3 sentences)
   - Brief overview of meeting purpose and key outcomes

3. **Key Discussion Topics**
   - Organize discussions by theme/topic
   - Summarize main points without excessive detail
   - Include relevant context and decisions made

4. **Action Items**
   - Clear, actionable tasks
   - Extract or infer owners when possible
   - Note deadlines or timeframes mentioned
   - **IMPORTANT**: When a relative date is mentioned (e.g., "Wednesday", "Friday", "next week"):
     * Calculate the actual calendar date based on the meeting date
     * Format: "Due: [Day], ([DD-MM-YYYY])"
     * Example: If meeting is Monday Aug 26, 2025 and deadline is "Wednesday", write "Due: Wednesday, (28-08-2025)"
   - Format: "- [Action item description] - Owner: [Name if mentioned] - Due: [Day/timeframe], ([calculated date if possible])"

5. **Decisions Made**
   - List key decisions and their rationale
   - Include any alternatives considered

6. **Questions & Concerns Raised**
   - Important questions asked during the meeting
   - Outstanding issues that need resolution

7. **Next Steps**
   - Follow-up meetings scheduled
   - Dependencies or blockers identified
   - Next milestones

8. **Additional Notes** (if applicable)
   - Any other relevant information
   - References or resources mentioned

Focus on clarity, conciseness, and actionability. Exclude technical issues, audio problems, 
and other meeting logistics that don't contribute to the meeting's substance.

**CRITICAL - Date Calculation for Action Items:**
When action items mention relative dates (e.g., "Wednesday", "Friday", "next week", "tomorrow", "today", "day after tomorrow", "by Monday"), 
EOD should be interpreted as the end of that day. In such cases, day should be considered as today's date. For example, if the meeting is on Tuesday and an action item is due "Tuesday" (e.g., "August 26, 2025" = Tuesday),
you MUST calculate the actual calendar date:
1. Extract the meeting date from the metadata (e.g., "August 26, 2025" = Tuesday)
2. Calculate the target date based on the reference (e.g., "Wednesday" = August 27, 2025)
3. Format as: "Due: [Day], ([DD-MM-YYYY])"

Examples:
- Meeting date: Tuesday, August 26, 2025
- "by Wednesday" → "Due: Wednesday, (27-08-2025)"
- "next Friday" → "Due: Friday, (05-09-2025)" 
- "by end of week" → "Due: Friday, (29-08-2025)"
- "next week" → "Due: Week of (01-09-2025 to 05-09-2025)"

If no specific timeframe is mentioned, write "Due: Not specified"

Use proper Markdown formatting with headers (##, ###), bullet points, and bold text where appropriate.
"""
        expected_output = (
            "A well-structured Markdown document containing professional Minutes of Meeting "
            "with all sections properly formatted and organized. "
            "CRITICAL: All content MUST come from the actual transcript data - no invented information."
        )
    
    else:  # json format
        description = f"""
CRITICAL: You MUST use the ReviewedTranscriptReader tool on '{transcript_path}' FIRST before writing anything.

STRICT REQUIREMENTS:
1. ONLY use information from the tool output - DO NOT invent or assume any details
2. If the tool returns meeting metadata, use EXACTLY that information
3. ONLY include topics, discussions, and action items that are ACTUALLY present in the transcript
4. If information is missing, use null or empty arrays rather than inventing details
5. DO NOT add fictional names, dates, or content that doesn't exist in the source data

After calling the tool and receiving the structured data, generate a comprehensive Minutes of Meeting in JSON format
using ONLY the actual data provided.

Return a JSON object with the following structure:
{{
  "meeting_info": {{
    "title": "Meeting title",
    "date": "Date",
    "time": "Time range",
    "team": "Team name",
    "participants": "Participant info"
  }},
  "executive_summary": "Brief 2-3 sentence overview",
  "key_topics": [
    {{
      "topic": "Topic name",
      "summary": "Discussion summary",
      "key_points": ["Point 1", "Point 2"]
    }}
  ],
  "action_items": [
    {{
      "description": "Action item",
      "owner": "Person responsible (if mentioned)",
      "due_date": "Deadline with calculated date (e.g., 'Wednesday, (27-08-2025)')",
      "due_date_calculated": "DD-MM-YYYY format if relative date mentioned",
      "priority": "high/medium/low"
    }}
  ],
  "decisions": [
    {{
      "decision": "What was decided",
      "rationale": "Why it was decided",
      "alternatives_considered": ["Alternative 1", "Alternative 2"]
    }}
  ],
  "questions_and_concerns": [
    "Question or concern raised"
  ],
  "next_steps": [
    "Next step or follow-up action"
  ],
  "additional_notes": "Any other relevant information"
}}

Focus on extracting substantive content. Skip technical issues and meeting logistics.

**CRITICAL - Date Calculation:**
For action items with relative dates (e.g., "Wednesday", "next Friday"):
1. Parse the meeting date from metadata
2. Calculate the actual calendar date
3. Include both the day name and calculated date in DD-MM-YYYY format

Return ONLY valid JSON, no additional text or markdown formatting.
"""
        expected_output = (
            "A valid JSON object containing structured Minutes of Meeting data "
            "with all required fields properly populated."
        )
    
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        name="GenerateMinutesOfMeeting",
    )