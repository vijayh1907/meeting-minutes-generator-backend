import os
import json
import time
from crewAgent1 import main
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime

app = FastAPI()
next_id = None
file_path = None

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


def compare_and_flag_category_changes(received_data, output_dir = "outputs", filename="classified_transcripts.json"):
    file_path = os.path.join(output_dir, filename)
    # Load reference data
    with open(file_path, encoding="utf-8") as f:
        reference_data = json.load(f)
    
    # Build a lookup for reference categories (assuming matching by index)
    for idx, item in enumerate(received_data):
        # Defensive: check if index exists in reference
        if idx < len(reference_data):
            raw_trans_line_old = reference_data[idx].get("raw_transcript_line") 
            raw_trans_line_new = item.get("raw_transcript_line")
            if raw_trans_line_old == raw_trans_line_new:
                old_category = reference_data[idx].get("category")
                new_category = item.get("category")
                if new_category != old_category:
                    item["category"] = new_category
                    item["old_category"] = old_category 
        #else:
            #item["old_category"] = None
    return received_data


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
    global next_id, file_path
    # Get next id from meet_data.json
    # file_path is where classified_transcripts.json is stored post LLM processing
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
    

    # Write back to the file post checking id existance
    upsert_dict_to_json_list(meet_data)
    # python crewAgent1.py --input call_transcript.txt --out outputs
    # Call LLM processing script here with subprocess
    # Example: Call crewAgent1.main from another Python script

    input_file = str(transcriptFile.filename) #"call_transcript.txt"
    output_dir = "outputs"
    model = "openai/gpt-4o-mini"
    temperature = 0.1
    try:
        # if next_id is None:
        #     output_dir = "outputs"
        # else:
        #     output_dir = os.path.join("outputs", str(next_id))
        start_time = time.time()
        main(input_file, output_dir, model, temperature)
        end_time = time.time()
        exec_time = end_time - start_time
        minutes = int(exec_time // 60)
        seconds = int(exec_time % 60)
        print(f"Process execution time: {minutes} min {seconds} sec")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing transcript: {str(e)}")
    # Get this response from backend to be sent to UI for generated MOM display
    file_path = os.path.join(output_dir, "classified_transcripts.json")
    # Add counts from classified_transcripts.json
    meet_data.update(count_categories(file_path))
    mom = read_participants_from_json(filename=file_path)
    for item in mom:
        if item['confidence'] < 0.8 :
            item['needs_review'] = True
        else:
            item['needs_review'] = False

    return JSONResponse(content=mom) 


@app.post("/review_content_classify")
async def review_content(
    transcripts_reviewed: str = Form(...)  # JSON string, parse in backend
):
    transcripts_reviewed = json.loads(transcripts_reviewed) 
    result = compare_and_flag_category_changes(transcripts_reviewed)
    # Storing the result in reviewed_transcripts.json file with meeting_id key and value from meet_data.json 
    # and transcripts as another key with value as received_data  
    updated_transcripts = {}
    updated_transcripts['meeting_id'] = next_id
    updated_transcripts['transcripts'] = result
    output_dir = "outputs"
    reviewed_path = os.path.join(output_dir, "reviewed_transcripts.json")
    with open(reviewed_path,"w",encoding="utf-8" )as f:
        json.dump(updated_transcripts,f,indent=2)
    print(f"Reviewed transcripts saved to {reviewed_path}")
    return result

@app.get("/health")
def health():
    return {"status": "ok"}
