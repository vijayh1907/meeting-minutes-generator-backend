import os
import json
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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
        "discussion": discussion_count,
        "action": action_count,
        "question": question_count
    }


def append_dict_to_json_list(new_dict, filename="meet_data.json"):
    # Read existing list from JSON file
    if os.path.exists(filename):
        with open(filename, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []
    else:
        data = []
    # Append the new dictionary
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

# Below to be changed based on input structure to pass to backend
class Participant(BaseModel):
    id: str
    name: str
    email: str

# endpoint to be changed based on structure to pass to backend
@app.post("/add_participant")
def add_participant(participant: Participant):
    # Read existing participants
    mom = read_participants_from_json(filename="classified_transcripts.json")
    meet_data = {}
    for item in mom:
        if item['confidence'] < 0.8 :
            item['needs_review'] = True
        else:
            item['needs_review'] = False
    
    # Example usage:
    meet_data = count_categories()
    # Get this from input structure
    meet_data['title'] = 'Sample meet'
    meet_data['date'] = '2025-01-2024'
    meet_data['status'] = 'Processing'
    meet_data['fileName'] = 'sample.txt'
    meet_data['fileSize'] = '2MB'
    meet_data['createdAt'] = '2025-01-24T10:00:00Z'
    meet_data['lastModified'] = '2025-01-24T10:00:00Z'
    meet_data['emailSent'] = False
    meet_data['participants'] = read_participants_from_json(filename='participants.json')
    

    # Write back to the file
    append_dict_to_json_list(meet_data)

    return JSONResponse(content=mom) 



@app.get("/health")
def health():
    return {"status": "ok"}
