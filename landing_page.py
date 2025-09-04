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
    print(f"[DEBUG] read_meetings_from_json: Reading from {filename}")
    if not os.path.exists(filename):
        print(f"[DEBUG] read_meetings_from_json: File not found: {filename}")
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    try:
        with open(filename, encoding='utf-8') as jsonfile:
            meetings = json.load(jsonfile)
        print(f"[DEBUG] read_meetings_from_json: Successfully read {len(meetings) if meetings else 0} meetings")
        return meetings
    except Exception as e:
        print(f"[DEBUG] read_meetings_from_json: Error reading file: {e}")
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
    print(f"[DEBUG] upsert_dict_to_json_list: Writing to {filename}")
    print(f"[DEBUG] upsert_dict_to_json_list: New dict ID: {new_dict.get('id')}")
    
    # Read existing list from JSON file
    try:
        if os.path.exists(filename):
            print(f"[DEBUG] upsert_dict_to_json_list: Reading existing file")
            with open(filename, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print(f"[DEBUG] upsert_dict_to_json_list: Existing data is not a list, creating new list")
                data = []
            else:
                print(f"[DEBUG] upsert_dict_to_json_list: Found {len(data)} existing items")
        else:
            print(f"[DEBUG] upsert_dict_to_json_list: File doesn't exist, creating new")
            data = []
        
        # Check if id exists and update, else append
        updated = False
        for idx, item in enumerate(data):
            if str(item.get("id")) == str(new_dict.get("id")):
                print(f"[DEBUG] upsert_dict_to_json_list: Updating existing item at index {idx}")
                data[idx] = new_dict
                updated = True
                break
        
        if not updated:
            print(f"[DEBUG] upsert_dict_to_json_list: Adding new item")
            data.append(new_dict)
        
        # Write back to the file
        print(f"[DEBUG] upsert_dict_to_json_list: Writing {len(data)} items to file")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[DEBUG] upsert_dict_to_json_list: Successfully written to file")
        
    except Exception as e:
        print(f"[DEBUG] upsert_dict_to_json_list: Error: {e}")
        raise e


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


@app.get("/api/meetings")
def get_meetings():
    meetings = read_meetings_from_json()
    return JSONResponse(content=meetings)

@app.get("/api/participants")
def get_participant_list():
    participants = read_participants_from_json()
    return JSONResponse(content=participants)

# API for post generate MOM
# 1. Post input data structure to backend process, LLM call and return response
# 2. Received response and apply logic to check confidence score and add 'needs_review' flag if below threshold and save structure
# 3. Return that structure to UI for display on ReviewScreen page
# 4. Another function to count no of discussions,questions and Action , add to the new structure along with other meeting details and add dictionary to list in meet_data.json

# Post API needs to be integrated with UI to refelect post request hit once generate MOM is clicked
@app.post("/api/upload_meeting_files")
async def upload_meeting_files(
    meetingTitle: str = Form(...),
    meetingDate: str = Form(...),
    participants: str = Form(...),  # JSON string, parse in backend
    transcriptFile: UploadFile = File(...),
    attachments: Optional[List[UploadFile]] = File(None)
):
    global next_id, file_path
    
    print(f"[DEBUG] === Starting upload_meeting_files ===")
    print(f"[DEBUG] Received parameters:")
    print(f"[DEBUG]   - meetingTitle: {meetingTitle}")
    print(f"[DEBUG]   - meetingDate: {meetingDate}")
    print(f"[DEBUG]   - participants: {participants}")
    print(f"[DEBUG]   - transcriptFile: {transcriptFile.filename if transcriptFile else 'None'}")
    print(f"[DEBUG]   - transcriptFile.size: {transcriptFile.size if transcriptFile else 'None'}")
    
    try:
        # Get next id from meet_data.json
        # file_path is where classified_transcripts.json is stored post LLM processing
        print(f"[DEBUG] Getting next ID from meet_data.json...")
        try:
            meetings = read_meetings_from_json()
            if meetings and isinstance(meetings, list):
                max_id = max(int(m.get("id", 0)) for m in meetings)
                next_id = str(max_id + 1)
                print(f"[DEBUG] Found existing meetings, next_id: {next_id}")
            else:
                next_id = "1"
                print(f"[DEBUG] No existing meetings, starting with id: {next_id}")
        except Exception as e:
            print(f"[DEBUG] Error reading meetings, using default id: {e}")
            next_id = "1"

        print(f"[DEBUG] Creating meeting data structure...")
        meet_data = {}
        meet_data['id'] = next_id
        # Getting parameters from UI form data
        meet_data['title'] = meetingTitle
        meet_data['date'] = meetingDate
        meet_data['status'] = 'processing'
        meet_data['fileName'] = transcriptFile.filename
        
        print(f"[DEBUG] Reading transcript file...")
        # Get file size in KB
        try:
            contents = await transcriptFile.read()
            file_size_kb = len(contents) / 1024
            await transcriptFile.seek(0)  # Reset file pointer if you need to read again
            meet_data['fileSize'] = f"{file_size_kb:.2f} KB"
            print(f"[DEBUG] File read successfully, size: {meet_data['fileSize']}")
        except Exception as e:
            print(f"[DEBUG] Error reading file: {e}")
            raise HTTPException(status_code=500, detail=f"Error reading transcript file: {str(e)}")
        
        meet_data['createdAt'] = datetime.now().isoformat()
        meet_data['lastModified'] = datetime.now().isoformat()
        meet_data['emailSent'] = False 

        # Below logic updated to put selected participants from UI and update  and then read it
        print(f"[DEBUG] Parsing participants JSON...")
        try:
            meet_data['participants'] = json.loads(participants)
            print(f"[DEBUG] Participants parsed successfully: {meet_data['participants']}")
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON decode error: {e}")
            raise HTTPException(status_code=422, detail=f"Invalid JSON format for participants: {str(e)}")
        except Exception as e:
            print(f"[DEBUG] Unexpected error parsing participants: {e}")
            raise HTTPException(status_code=500, detail=f"Error parsing participants: {str(e)}")
        

        # Write back to the file post checking id existance
        print(f"[DEBUG] Saving meeting data to JSON...")
        try:
            upsert_dict_to_json_list(meet_data)
            print(f"[DEBUG] Meeting data saved successfully")
        except Exception as e:
            print(f"[DEBUG] Error saving meeting data: {e}")
            raise HTTPException(status_code=500, detail=f"Error saving meeting data: {str(e)}")
        
        # python crewAgent1.py --input call_transcript.txt --out outputs
        # Call LLM processing script here with subprocess
        # Example: Call crewAgent1.main from another Python script

        print(f"[DEBUG] Starting LLM processing...")
        input_file = str(transcriptFile.filename) #"call_transcript.txt"
        output_dir = "outputs"
        model = "openai/gpt-4o-mini"
        temperature = 0.1
        
        print(f"[DEBUG]   - input_file: {input_file}")
        print(f"[DEBUG]   - output_dir: {output_dir}")
        print(f"[DEBUG]   - model: {model}")
        print(f"[DEBUG]   - temperature: {temperature}")
        
        try:
            # if next_id is None:
            #     output_dir = "outputs"
            # else:
            #     output_dir = os.path.join("outputs", str(next_id))
            start_time = time.time()
            print(f"[DEBUG] Calling main() function...")
            main(input_file, output_dir, model, temperature)
            end_time = time.time()
            exec_time = end_time - start_time
            minutes = int(exec_time // 60)
            seconds = int(exec_time % 60)
            print(f"[DEBUG] LLM processing completed successfully")
            print(f"Process execution time: {minutes} min {seconds} sec")
        except Exception as e:
            print(f"[DEBUG] Error in LLM processing: {e}")
            print(f"[DEBUG] Error type: {type(e).__name__}")
            import traceback
            print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error processing transcript: {str(e)}")
        
        # Get this response from backend to be sent to UI for generated MOM display
        file_path = os.path.join(output_dir, "classified_transcripts.json")
        print(f"[DEBUG] Looking for output file: {file_path}")
        
        # Check if output file exists
        if not os.path.exists(file_path):
            print(f"[DEBUG] ERROR: Output file not found: {file_path}")
            raise HTTPException(status_code=500, detail="LLM processing output file not found")
        
        print(f"[DEBUG] Output file found, processing results...")
        
        # Add counts from classified_transcripts.json
        try:
            print(f"[DEBUG] Counting categories...")
            meet_data.update(count_categories(file_path))
            print(f"[DEBUG] Categories counted successfully")
        except Exception as e:
            print(f"[DEBUG] Error counting categories: {e}")
            raise HTTPException(status_code=500, detail=f"Error counting categories: {str(e)}")
        
        # Read the processed transcripts
        try:
            print(f"[DEBUG] Reading transcripts from: {file_path}")
            mom = read_participants_from_json(filename=file_path)
            print(f"[DEBUG] Transcripts read successfully, count: {len(mom) if mom else 0}")
        except Exception as e:
            print(f"[DEBUG] Error reading transcripts: {e}")
            raise HTTPException(status_code=500, detail=f"Error reading transcripts: {str(e)}")
        
        # Process confidence scores
        print(f"[DEBUG] Processing confidence scores...")
        for item in mom:
            if item['confidence'] <= 0.8 :
                item['needs_review'] = True
            else:
                item['needs_review'] = False

        print(f"[DEBUG] === Processing completed successfully ===")
        return JSONResponse(content=mom)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        print(f"[DEBUG] Re-raising HTTP exception")
        raise
    except Exception as e:
        print(f"[DEBUG] === UNEXPECTED ERROR ===")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 


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

@app.post("/api/test_upload")
async def test_upload(
    meetingTitle: str = Form(...),
    meetingDate: str = Form(...),
    participants: str = Form(...),
    transcriptFile: UploadFile = File(...)
):
    """
    Test endpoint to validate form data without processing
    """
    print(f"[DEBUG] === Test Upload Endpoint ===")
    print(f"[DEBUG] Received: {meetingTitle}, {meetingDate}, {participants}, {transcriptFile.filename}")
    
    try:
        # Test JSON parsing
        participants_data = json.loads(participants)
        print(f"[DEBUG] Participants parsed: {participants_data}")
        
        # Test file reading
        contents = await transcriptFile.read()
        file_size = len(contents)
        print(f"[DEBUG] File size: {file_size} bytes")
        
        return {
            "message": "Form data received successfully",
            "meetingTitle": meetingTitle,
            "meetingDate": meetingDate,
            "participants": participants_data,
            "filename": transcriptFile.filename,
            "file_size": file_size
        }
    except json.JSONDecodeError as e:
        print(f"[DEBUG] JSON error: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        print(f"[DEBUG] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
