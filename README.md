# 📝 Meeting Minutes Generator (CrewAI + FastAPI)

A comprehensive AI-powered system for automatically generating professional Minutes of Meeting (MoM) from meeting transcripts using [CrewAI](https://github.com/joaomdmoura/crewai) agents and FastAPI middleware.

## 🎯 Overview

This system transforms raw meeting transcripts into structured, professional meeting minutes through a three-stage CrewAI pipeline:

1. **Stage 1 (crewAgent1)**: Classify transcript lines into Action/Question/Discussion categories
2. **Stage 2 (crewAgent2)**: Generate comprehensive Minutes of Meeting with action items
3. **Stage 3 (crewAgent3)**: Merge reviewed/updated action items back into the MoM

Optional features:
- **FastAPI Middleware**: RESTful API endpoints for web integration
- **Slack Integration**: Automated notifications with action item summaries

---

## 📂 Project Structure

```
.
├── crewAgent1.py                           # Stage 1: Transcript Classification
├── crewAgent2.py                           # Stage 2: MoM Generation
├── crewAgent3.py                           # Stage 3: Action Items Merger
├── landing_page.py                         # FastAPI REST API Server
├── quick_slack_notify.py                   # Slack Notification Script
├── call_transcript.txt                     # Example input transcript
├── .env                                    # Environment variables (API keys)
├── requirements.txt                        # Python dependencies
│
├── src/
│   ├── agents/
│   │   ├── meeting_classifier_agent.py     # Classifier agent definition
│   │   ├── mom_generator_agent.py          # MoM generator agent
│   │   └── mom_merger_agent.py             # Action items merger agent
│   │
│   ├── tasks/
│   │   ├── classify_task.py                # Classification task logic
│   │   ├── mom_generation_task.py          # MoM generation task
│   │   └── mom_merge_task.py               # Merge task logic
│   │
│   ├── tools/
│   │   ├── transcript_reader_tool.py       # Reads .txt/.docx/.pdf transcripts
│   │   ├── reviewed_transcript_reader_tool.py  # Reads classified JSON
│   │   └── mom_and_action_items_reader_tool.py # Reads MoM + action items
│   │
│   └── io_utils.py                         # JSON/CSV utility functions
│
└── outputs/                                # Generated outputs directory
    ├── classified_transcripts.json         # Stage 1 output
    ├── classified_transcripts.csv          # Stage 1 output (CSV)
    ├── reviewed_transcripts.json           # Stage 1 output (renamed for stage 2)
    ├── minutes_of_meeting.md               # Stage 2 output
    ├── action_items.json                   # Stage 2/3 output
    └── minutes_of_meeting_backup_*.md      # Automatic backups
```

---

## ⚙️ Installation

### 1. Clone and Setup Virtual Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd <project-directory>

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate    # Linux/Mac
venv\Scripts\activate       # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `crewai` - Multi-agent orchestration framework
- `langchain-openai` - OpenAI LLM integration
- `python-docx` - Word document processing
- `pypdf` - PDF processing
- `pandas` - Data manipulation
- `python-dotenv` - Environment variable management
- `fastapi` - API framework
- `uvicorn` - ASGI server
- `requests` - HTTP library for Slack

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-...

# Optional (for Slack notifications)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

---

## 🚀 Usage

### Complete Workflow (All Stages)

```bash
# Stage 1: Classify transcript lines
python crewAgent1.py --input call_transcript.txt --out outputs

# Stage 2: Generate Minutes of Meeting
python crewAgent2.py --input outputs/reviewed_transcripts.json --out outputs

# Stage 3: Merge reviewed action items (if you've updated action_items.json)
python crewAgent3.py --mom outputs/minutes_of_meeting.md --items outputs/action_items.json

# Optional: Send Slack notification
python quick_slack_notify.py
```

---

## 📋 Stage-by-Stage Guide

### Stage 1: Transcript Classification (crewAgent1.py)

**Purpose**: Classify each line of a meeting transcript into categories.

**Input**: Raw transcript file (`.txt`, `.docx`, or `.pdf`)

**Output**: 
- `classified_transcripts.json` - Full classification results
- `classified_transcripts.csv` - Same data in CSV format

**Command**:
```bash
python crewAgent1.py --input call_transcript.txt --out outputs
```

**Options**:
- `--input` - Path to transcript file (required)
- `--out` - Output directory (default: `outputs`)
- `--model` - LLM model (default: `openai/gpt-4o-mini`)
- `--temperature` - Temperature 0-1 (default: `0.1`)

**Output Format**:
```json
[
  {
    "raw_transcript_line": "Good morning everyone, let's get started.",
    "category": "Discussion",
    "tags": ["greeting", "meeting-start"],
    "confidence": 0.9,
    "notes": "Opening greeting to start the meeting"
  },
  {
    "raw_transcript_line": "Can everyone see my screen?",
    "category": "Question",
    "tags": ["screen-check", "technical"],
    "confidence": 0.85,
    "notes": "Asking participants to confirm screen visibility"
  }
]
```

**Categories**:
- **Action**: Commitments, tasks, or decisions that require follow-up
- **Question**: Inquiries requiring answers or clarification
- **Discussion**: General conversation, explanations, or context

---

### Stage 2: Minutes of Meeting Generation (crewAgent2.py)

**Purpose**: Generate professional Minutes of Meeting from classified transcripts.

**Input**: `reviewed_transcripts.json` (output from Stage 1)

**Output**:
- `minutes_of_meeting.md` - Professional MoM in Markdown
- `action_items.json` - Extracted action items with metadata

**Command**:
```bash
python crewAgent2.py --input outputs/reviewed_transcripts.json --out outputs
```

**Options**:
- `--input` - Path to reviewed_transcripts.json (default: `outputs/reviewed_transcripts.json`)
- `--out` - Output directory (default: `outputs`)
- `--model` - LLM model (default: `openai/gpt-4o-mini`)
- `--temperature` - Temperature 0-1 (default: `0.2`)
- `--format` - Output format: `markdown`, `json`, or `both` (default: `markdown`)

**Generated MoM Structure**:
```markdown
# Financial Forecasting Team Meeting

### Date and Time
**Date:** November 1, 2025  
**Time:** 10:00 AM - 11:30 AM

### Team/Department
Retail Financial Forecasting

### Participants/Attendees
8 team members

### Executive Summary
Brief overview of meeting purpose and key outcomes...

### Key Discussion Topics
#### Topic 1: Q3 Forecasting Model Performance
Discussion summary...

### Action Items
- **Share the agenda for today's sprint review** - Owner: John Doe (john@example.com) - Due: Monday, (03-11-2025) - Priority: Medium - Status: Pending

### Decisions Made
- Decision 1...

### Questions & Concerns Raised
- Question 1...

### Next Steps
- Follow-up meeting scheduled...
```

**Action Items JSON Structure**:
```json
{
  "meeting_date": "November 1, 2025",
  "generated_at": "2025-11-03T10:30:00",
  "total_items": 5,
  "action_items": [
    {
      "id": "action_001",
      "description": "Share the agenda for today's sprint review",
      "owner": {
        "name": "John Doe",
        "email": "john@example.com"
      },
      "due_date": "Monday, (03-11-2025)",
      "due_date_calculated": "03-11-2025",
      "status": "pending",
      "created_from_meeting": "November 1, 2025",
      "priority": "medium",
      "tags": []
    }
  ]
}
```

---

### Stage 3: Action Items Merger (crewAgent3.py)

**Purpose**: Merge reviewed/updated action items back into the MoM.

**Use Case**: After reviewing action items (updating owners, due dates, priorities, status), merge them back into the official Minutes of Meeting.

**Input**:
- `minutes_of_meeting.md` - Original MoM
- `action_items.json` - Reviewed/updated action items

**Output**:
- Updated `minutes_of_meeting.md` with new action items
- Updated `action_items.json` extracted from merged MoM
- Backup of original MoM (optional)

**Command**:
```bash
python crewAgent3.py --mom outputs/minutes_of_meeting.md --items outputs/action_items.json
```

**Options**:
- `--mom` - Path to MoM file (default: `outputs/minutes_of_meeting.md`)
- `--items` - Path to action_items.json (default: `outputs/action_items.json`)
- `--out` - Output directory (default: `outputs`)
- `--model` - LLM model (default: `openai/gpt-4o-mini`)
- `--temperature` - Temperature (default: `0.2`)
- `--no-backup` - Don't create backup of original MoM

**Key Features**:
- ✅ Updates ONLY the Action Items section
- ✅ Preserves all other MoM sections unchanged
- ✅ Calculates missing due dates based on meeting date
- ✅ Handles relative dates ("Monday", "Wednesday", "next week", "EOD")
- ✅ Creates automatic backups
- ✅ Re-extracts action items to keep JSON in sync

**Date Calculation Logic**:
```python
Meeting Date: November 1, 2025 (Friday)

"Monday" → "Monday, (03-11-2025)"
"Wednesday" → "Wednesday, (05-11-2025)"
"Today" → "Friday, (01-11-2025)"
"Tomorrow" → "Saturday, (02-11-2025)"
"End of this week" → "Sunday, (03-11-2025)"
"Next week" → "Week of (04-11-2025 to 08-11-2025)"
```

---

## 🌐 API Middleware (landing_page.py)

### Overview

FastAPI-based REST API server for integrating the MoM pipeline into web applications.

### Starting the Server

```bash
# Development mode (auto-reload)
uvicorn landing_page:app --reload

# Production mode (specific host/port)
uvicorn landing_page:app --host 0.0.0.0 --port 9000 --reload
```

### API Endpoints

#### 1. Health Check
```bash
GET /
```

**Response**:
```json
{
  "message": "Welcome to Meeting Minutes Generator API",
  "status": "running",
  "endpoints": {
    "classify": "/api/classify",
    "generate_mom": "/api/generate-mom",
    "merge_action_items": "/api/merge-action-items",
    "slack_notify": "/api/slack-notify"
  }
}
```

#### 2. Classify Transcript (Stage 1)
```bash
POST /api/classify
Content-Type: multipart/form-data

transcript: <file>
model: openai/gpt-4o-mini (optional)
temperature: 0.1 (optional)
```

**Example with curl**:
```bash
curl -X POST "http://127.0.0.1:8000/api/classify" \
  -F "transcript=@call_transcript.txt" \
  -F "model=openai/gpt-4o-mini" \
  -F "temperature=0.1"
```

**Response**:
```json
{
  "status": "success",
  "message": "Transcript classified successfully",
  "total_items": 150,
  "files": {
    "json": "outputs/classified_transcripts.json",
    "csv": "outputs/classified_transcripts.csv"
  }
}
```

#### 3. Generate MoM (Stage 2)
```bash
POST /api/generate-mom

{
  "input_path": "outputs/reviewed_transcripts.json",
  "model": "openai/gpt-4o-mini",
  "temperature": 0.2,
  "output_format": "markdown"
}
```

**Example**:
```bash
curl -X POST "http://127.0.0.1:8000/api/generate-mom" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "outputs/reviewed_transcripts.json",
    "output_format": "markdown"
  }'
```

**Response**:
```json
{
  "status": "success",
  "message": "Minutes of Meeting generated successfully",
  "files": {
    "mom": "outputs/minutes_of_meeting.md",
    "action_items": "outputs/action_items.json"
  },
  "total_action_items": 8
}
```

#### 4. Merge Action Items (Stage 3)
```bash
POST /api/merge-action-items

{
  "mom_path": "outputs/minutes_of_meeting.md",
  "action_items_path": "outputs/action_items.json",
  "model": "openai/gpt-4o-mini",
  "temperature": 0.2,
  "backup": true
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Action items merged successfully",
  "files": {
    "updated_mom": "outputs/minutes_of_meeting.md",
    "action_items_json": "outputs/action_items.json"
  },
  "total_action_items": 8
}
```

#### 5. Slack Notification
```bash
POST /api/slack-notify

{
  "action_items_path": "outputs/action_items.json"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Slack notification sent successfully",
  "items_sent": 5
}
```

---

## 📱 Slack Integration (quick_slack_notify.py)

### Setup

1. Create a Slack Incoming Webhook:
   - Go to https://api.slack.com/apps
   - Create a new app or select existing
   - Enable Incoming Webhooks
   - Add webhook to your workspace
   - Copy the webhook URL

2. Add to `.env`:
```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX
```

### Sending Notifications

```bash
python quick_slack_notify.py
```

**What it sends**:
- Meeting date and time
- Total action items count
- First 5 action items with:
  - Priority indicators (🔴 High, 🟡 Medium, 🟢 Low)
  - Description
  - Owner name
  - Due date
- Link to full MoM

**Example Slack Message**:
```
📋 Meeting Minutes Updated

Meeting Date: November 1, 2025
Total Action Items: 8

🎯 Action Items:

1. 🟡 Share the agenda for today's sprint review
   👤 John Doe | 📅 Monday, (03-11-2025)

2. 🔴 Complete Q4 forecast model
   👤 Jane Smith | 📅 Friday, (07-11-2025)

...and 3 more items

💡 Check the updated Minutes of Meeting for full details
```

---

## 🎨 Key Features

### Intelligent Date Calculation
- Automatically calculates calendar dates from relative dates
- Handles: "Today", "Tomorrow", "Monday", "Next week", "EOD"
- All dates formatted as: "Day, (DD-MM-YYYY)"

### Anti-Hallucination Measures
- Agents instructed to ONLY use information from source transcripts
- No invented names, dates, or content
- States "Not specified" when information is missing
- Low temperature settings (0.1-0.2) for precise outputs

### Professional Formatting
- Clean markdown structure
- Scannable headers and bullet points
- Bold emphasis for key information
- Consistent formatting across all outputs

### Automatic Backups
- Creates timestamped backups before updates
- Preserves original MoM files
- Rollback capability if needed

### Modular Architecture
- Separate agents for each stage
- Reusable tools and tasks
- Easy to extend or customize
- Clean separation of concerns

---

## 🔧 Configuration

### Model Selection

Recommended models by use case:

```bash
# Fast and cost-effective (default)
--model openai/gpt-4o-mini

# Higher quality for complex meetings
--model openai/gpt-4o

# Alternative providers (if configured)
--model anthropic/claude-3-sonnet
--model google/gemini-pro
```

### Temperature Settings

```bash
# Classification (Stage 1) - Precise categorization
--temperature 0.1

# Generation (Stage 2) - Balanced creativity
--temperature 0.2

# Merging (Stage 3) - Precise updates only
--temperature 0.2
```

---

## 📊 Example Workflow

### Scenario: Weekly Team Meeting

```bash
# 1. Record meeting and save transcript as meeting_transcript.txt

# 2. Classify the transcript
python crewAgent1.py \
  --input meeting_transcript.txt \
  --out outputs \
  --temperature 0.1

# Output: outputs/classified_transcripts.json

# 3. Rename for next stage (or just use as-is)
cp outputs/classified_transcripts.json outputs/reviewed_transcripts.json

# 4. Generate Minutes of Meeting
python crewAgent2.py \
  --input outputs/reviewed_transcripts.json \
  --out outputs \
  --format markdown

# Output: 
#   - outputs/minutes_of_meeting.md
#   - outputs/action_items.json

# 5. Review and update action_items.json
#    - Assign owners
#    - Set due dates
#    - Adjust priorities
#    - Update status

# 6. Merge reviewed action items back
python crewAgent3.py \
  --mom outputs/minutes_of_meeting.md \
  --items outputs/action_items.json

# Output: Updated MoM with reviewed action items

# 7. Send Slack notification
python quick_slack_notify.py

# Done! ✅
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "File not found" error
```bash
# Ensure you're in the project root directory
pwd

# Check if outputs directory exists
ls -la outputs/

# Use absolute paths if needed
python crewAgent2.py --input /full/path/to/reviewed_transcripts.json
```

#### 2. OpenAI API errors
```bash
# Check your API key
echo $OPENAI_API_KEY

# Verify .env file exists
cat .env

# Test API key with curl
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

#### 3. Module import errors
```bash
# Ensure virtual environment is activated
which python

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Check Python version (requires 3.9+)
python --version
```

#### 4. Slack webhook not working
```bash
# Test webhook directly
curl -X POST YOUR_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test message"}'

# Check .env file
cat .env | grep SLACK_WEBHOOK_URL
```

---

## 🧪 Testing

### Run Individual Stages

```bash
# Test classification only
python crewAgent1.py --input call_transcript.txt --out test_outputs

# Test MoM generation only (requires classified_transcripts.json)
python crewAgent2.py --input test_outputs/reviewed_transcripts.json --out test_outputs

# Test action items merger only (requires both MoM and action_items)
python crewAgent3.py \
  --mom test_outputs/minutes_of_meeting.md \
  --items test_outputs/action_items.json \
  --out test_outputs
```

### Verify Output Quality

```bash
# Check JSON structure
python -m json.tool outputs/action_items.json

# View MoM in terminal
cat outputs/minutes_of_meeting.md

# Count action items
jq '.total_items' outputs/action_items.json
```

---

## 📈 Performance Tips

1. **Use GPT-4o-mini for most tasks** - 10x cheaper, adequate quality
2. **Use GPT-4o for critical meetings** - Better comprehension, fewer hallucinations
3. **Adjust temperature**:
   - Lower (0.1) for factual extraction
   - Higher (0.3) for creative summaries
4. **Batch process** - Process multiple transcripts together for cost efficiency
5. **Cache results** - Save intermediate outputs for troubleshooting

---

## 🔐 Security Notes

- Never commit `.env` file to version control
- Use environment-specific `.env` files (`.env.production`, `.env.development`)
- Rotate API keys regularly
- Use read-only API keys when possible
- Sanitize sensitive information from transcripts before processing

---

## 📚 Additional Resources

- [CrewAI Documentation](https://docs.crewai.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional output formats (HTML, PDF)
- More LLM provider integrations
- Enhanced action item tracking
- Meeting analytics dashboard
- Video transcript support
- Multi-language support

---

## 📝 License

[Your License Here]

---

## 🙋 Support

For issues or questions:
- Open a GitHub issue
- Contact: [Your Contact Info]
- Documentation: [Your Docs URL]

---

**Built with using CrewAI, FastAPI, and OpenAI**