import os
import json
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime

app = FastAPI()

# Allow requests from your frontend (e.g., http://localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify ["http://localhost:8000"] for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_meetings_from_json(filename="meet_data.json"):
    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    try:
        with open(filename, encoding='utf-8') as jsonfile:
            meetings = json.load(jsonfile)
        return meetings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading {filename}: {str(e)}")


def count_categories(filename="classified_transcripts.json"):
    with open(filename, encoding="utf-8") as f:
        data = json.load(f)
    discussion_count = sum(1 for item in data if item.get("category") == "Discussion")
    action_count = sum(1 for item in data if item.get("category") == "Action")
    question_count = sum(1 for item in data if item.get("category") == "Question")
    return {
        "discussionCount": discussion_count,
        "actionCount": action_count,
        "questionCount": question_count
    }


def upsert_dict_to_json_list(new_dict, filename="meet_data.json"):
    # Read existing list from JSON file
    if os.path.exists(filename):
        with open(filename, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []
    else:
        data = []
     # Check if id exists and update, else append
    updated = False
    for idx, item in enumerate(data):
        if str(item.get("id")) == str(new_dict.get("id")):
            data[idx] = new_dict
            updated = True
            break
    if not updated:
        data.append(new_dict)
    # Write back to the file
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_participants_from_json(filename="participants.json"):
    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    try:
        with open(filename, encoding='utf-8') as jsonfile:
            meetings = json.load(jsonfile)
        return meetings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading {filename}: {str(e)}")


@app.get("/")
def get_meetings():
    meetings = read_meetings_from_json()
    return JSONResponse(content=meetings)

@app.get("/add_participant")
def get_participant_list():
    participants = read_participants_from_json()
    return JSONResponse(content=participants)

# API for post generate MOM
# 1. Post input data structure to backend process, LLM call and return response
# 2. Received response and apply logic to check confidence score and add 'needs_review' flag if below threshold and save structure
# 3. Return that structure to UI for display on ReviewScreen page
# 4. Another function to count no of discussions,questions and Action , add to the new structure along with other meeting details and add dictionary to list in meet_data.json

# Post API needs to be integrated with UI to refelect post request hit once generate MOM is clicked
@app.post("/upload_meeting_files")
async def upload_meeting_files(
    meetingTitle: str = Form(...),
    meetingDate: str = Form(...),
    participants: str = Form(...),  # JSON string, parse in backend
    transcriptFile: UploadFile = File(...),
    attachments: Optional[List[UploadFile]] = File(None)
):
    
    # Get next id from meet_data.json
    try:
        meetings = read_meetings_from_json()
        if meetings and isinstance(meetings, list):
            max_id = max(int(m.get("id", 0)) for m in meetings)
            next_id = str(max_id + 1)
        else:
            next_id = "1"
    except Exception:
        next_id = "1"

    meet_data = {}
    meet_data['id'] = next_id
    # Getting parameters from UI form data
    meet_data['title'] = meetingTitle
    meet_data['date'] = meetingDate
    meet_data['status'] = 'processing'
    meet_data['fileName'] = transcriptFile.filename
    
    # Get file size in KB
    contents = await transcriptFile.read()
    file_size_kb = len(contents) / 1024
    await transcriptFile.seek(0)  # Reset file pointer if you need to read again
    meet_data['fileSize'] = f"{file_size_kb:.2f} KB"
    
    meet_data['createdAt'] = datetime.now().isoformat()
    meet_data['lastModified'] = datetime.now().isoformat()
    meet_data['emailSent'] = False 

    # Below logic updated to put selected participants from UI and update  and then read it
    meet_data['participants'] = json.loads(participants)
    
    # Add counts from classified_transcripts.json
    meet_data.update(count_categories())

    # Write back to the file post checking id existance
    upsert_dict_to_json_list(meet_data)

    # Get this response from backend to be sent to UI for generated MOM display
    
    
    mom = read_participants_from_json(filename="classified_transcripts.json")
    for item in mom:
        if item['confidence'] < 0.8 :
            item['needs_review'] = True
        else:
            item['needs_review'] = False

    return JSONResponse(content=mom) 



@app.get("/health")
def health():
    return {"status": "ok"}
