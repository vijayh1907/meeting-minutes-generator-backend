import os
import json
import time
from crewAgent1 import main as crewAgent1_main
from crewAgent2 import main as crewAgent2_main
from crewAgent3 import main as crewAgent3_main
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime
from quick_slack_notify import main as slack_notify
from copy import deepcopy

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
        
        # Create meeting data dictionary
        meet_data = {
            "id": next_id,
            "title": meetingTitle,
            "date": meetingDate,
            "fileName": transcriptFile.filename,
        }
        
        # Save uploaded transcript file
        print(f"[DEBUG] Saving transcript file...")
        try:
            contents = await transcriptFile.read()
            meet_data['fileSize'] = len(contents)
            with open(transcriptFile.filename, "wb") as f:
                f.write(contents)
            print(f"[DEBUG] File saved: {transcriptFile.filename}")
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
            crewAgent1_main(input_file, output_dir, model, temperature)
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
            # append meeting_id or next_id
            mom.append({'meeting_id': next_id, 'confidence' : 1.0 , 'category' : 'pointer','needs_review':'false' , 'notes' : 'meeting id' , 'raw_transcript_line': 'meeting id', 'tags' : ''})  # Dummy confidence for meeting_id entry
            mom.append({'next_id': next_id, 'confidence' : 1.0 , 'category' : 'pointer','needs_review':'false' , 'notes' : 'meeting id' , 'raw_transcript_line': 'meeting id', 'tags' : ''})  # Dummy confidence for meeting_id entry
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


def process_mom_and_action_items(meeting_id=None, output_format="markdown"):
    """
    Helper function to generate MoM and Action Items from reviewed transcripts.
    Can be called from endpoints or other functions.
    """
    global next_id
    
    print(f"[DEBUG] === Starting process_mom_and_action_items ===")
    print(f"[DEBUG]   - meeting_id: {meeting_id or next_id}")
    print(f"[DEBUG]   - output_format: {output_format}")
    
    try:
        current_meeting_id = meeting_id or next_id
        if not current_meeting_id:
            raise HTTPException(status_code=400, detail="Meeting ID not found.")
        
        # Define paths
        input_file = "outputs/reviewed_transcripts.json"
        output_dir = "outputs"
        model = "openai/gpt-4o-mini"
        temperature = 0.2
        
        # Check if input file exists
        if not os.path.exists(input_file):
            raise HTTPException(
                status_code=404, 
                detail=f"Reviewed transcripts file not found at {input_file}"
            )
        
        print(f"[DEBUG] Starting MoM generation with crewAgent2...")
        
        # Call crewAgent2.main
        start_time = time.time()
        crewAgent2_main(
            in_path=input_file,
            out_dir=output_dir,
            model=model,
            temperature=temperature,
            output_format=output_format
        )
        end_time = time.time()
        exec_time = end_time - start_time
        minutes = int(exec_time // 60)
        seconds = int(exec_time % 60)
        print(f"[DEBUG] MoM generation completed in {minutes} min {seconds} sec")
        
        # Prepare response data
        response_data = {
            "meeting_id": current_meeting_id,
            "status": "success",
            "message": "MoM and Action Items generated successfully",
            "execution_time": f"{minutes} min {seconds} sec",
            "files_generated": []
        }
        
        # Check for generated files
        mom_md_path = os.path.join(output_dir, "minutes_of_meeting.md")
        mom_json_path = os.path.join(output_dir, "minutes_of_meeting.json")
        action_items_path = os.path.join(output_dir, "action_items.json")
        
        if os.path.exists(mom_md_path):
            response_data["files_generated"].append({
                "type": "minutes_markdown",
                "path": mom_md_path,
                "size": os.path.getsize(mom_md_path)
            })
        
        if os.path.exists(mom_json_path):
            response_data["files_generated"].append({
                "type": "minutes_json",
                "path": mom_json_path,
                "size": os.path.getsize(mom_json_path)
            })
        
        # Read and include action items
        if os.path.exists(action_items_path):
            with open(action_items_path, 'r', encoding='utf-8') as f:
                action_items_data = json.load(f)
            
            response_data["files_generated"].append({
                "type": "action_items_json",
                "path": action_items_path,
                "size": os.path.getsize(action_items_path)
            })
            
            response_data["action_items"] = action_items_data
            response_data["action_items_count"] = action_items_data.get("total_items", 0)
        
        print(f"[DEBUG] === MoM generation completed successfully ===")
        return response_data
        
    except Exception as e:
        print(f"[DEBUG] Error in process_mom_and_action_items: {e}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        raise



@app.post("/api/review content classify")  # Handle space-separated version from frontend
@app.post("/review_content_classify")  # Legacy endpoint support
async def review_content(
    transcripts_reviewed: List[dict]
):
    """Review content and automatically generate MoM and action items
    
    Accepts JSON body with array of classified transcript items.
    Each item should have: raw_transcript_line, category, tags, confidence, notes, meeting_id
    """
    global next_id
    try:
        # transcripts_reviewed is already parsed as a list from JSON body
        print(f"[DEBUG] Received {len(transcripts_reviewed)} transcript items")
        
        # Try to extract meeting_id from the transcript items
        meeting_title_from_payload = None
        if next_id is None and transcripts_reviewed:
            for item in transcripts_reviewed:
                if 'meeting_id' in item:
                    meeting_title_from_payload = item['meeting_id']
                    # Try to find matching meeting in meet_data.json by title
                    try:
                        meetings = read_meetings_from_json()
                        if meetings and isinstance(meetings, list):
                            for meeting in meetings:
                                if meeting.get("title") == meeting_title_from_payload:
                                    next_id = str(meeting.get("id", ""))
                                    print(f"[DEBUG] Found matching meeting in meet_data.json: id={next_id}, title={meeting_title_from_payload}")
                                    break
                        if next_id is None:
                            # If not found, use the title as meeting_id (string)
                            next_id = str(meeting_title_from_payload)
                            print(f"[DEBUG] No matching meeting found, using title as meeting_id: {next_id}")
                    except Exception as e:
                        print(f"[DEBUG] Error looking up meeting: {e}")
                        # Fallback: use the title as meeting_id
                        next_id = str(meeting_title_from_payload) if meeting_title_from_payload else None
                    break
        
        if next_id is None:
            # Last resort: use default ID
            print(f"[DEBUG] Warning: Could not determine meeting_id, using default")
            next_id = "1"
        
        print(f"[DEBUG] Starting review_content for meeting_id: {next_id}")
        result = compare_and_flag_category_changes(transcripts_reviewed)

        # Store reviewed transcripts
        updated_transcripts = {
            'meeting_id': next_id,
            'transcripts': result
        }
        output_dir = "outputs"
        reviewed_path = os.path.join(output_dir, "reviewed_transcripts.json")
        
        with open(reviewed_path, "w", encoding="utf-8") as f:
            json.dump(updated_transcripts, f, indent=2)
        
        print(f"[DEBUG] Reviewed transcripts saved to {reviewed_path}")
        
        # Now call the helper function to generate MoM and action items
        print(f"[DEBUG] Calling process_mom_and_action_items...")
        mom_response = process_mom_and_action_items(
            meeting_id=next_id,
            output_format="markdown"
        )
        
        print(f"[DEBUG] MoM generation completed")
        print(f"[DEBUG] Files generated: {len(mom_response.get('files_generated', []))}")
        
        # Return both the reviewed transcripts and MoM generation status
        return JSONResponse(content={
            "reviewed_transcripts": result,
            "identified_action_items": mom_response
        })
        
    except Exception as e:
        print(f"[DEBUG] Error in review_content: {e}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")



def compare_and_flag_action_item_changes(reviewed_items, original_data):
    """
    Compare reviewed action items with original items and flag changes.
    
    Args:
        reviewed_items: List of reviewed action items or dict with action_items key
        original_data: Original action items data (dict or None)
        
    Returns:
        List of action items with change flags added
    """
    # Extract the action items list from input
    if isinstance(reviewed_items, dict) and "action_items" in reviewed_items:
        reviewed_list = reviewed_items["action_items"]
    elif isinstance(reviewed_items, list):
        reviewed_list = reviewed_items
    else:
        print(f"[DEBUG] Warning: Unexpected reviewed_items format")
        return reviewed_items
    
    # Extract original action items list
    original_list = []
    if original_data:
        if isinstance(original_data, dict) and "action_items" in original_data:
            original_list = original_data["action_items"]
        elif isinstance(original_data, list):
            original_list = original_data
    
    # If no original data, return reviewed items as-is
    if not original_list:
        print(f"[DEBUG] No original items for comparison")
        return reviewed_list
    
    # Compare and flag changes
    print(f"[DEBUG] Comparing {len(reviewed_list)} reviewed items with {len(original_list)} original items")
    
    for idx, reviewed_item in enumerate(reviewed_list):
        # Find matching original item by ID or index
        original_item = None
        
        # Try to match by ID first
        if "id" in reviewed_item:
            reviewed_id = reviewed_item["id"]
            original_item = next((item for item in original_list if item.get("id") == reviewed_id), None)
        
        # Fall back to index matching
        if not original_item and idx < len(original_list):
            original_item = original_list[idx]
        
        if not original_item:
            # New item added during review
            reviewed_item["change_type"] = "added"
            continue
        
        # Compare fields and track changes
        changes = []
        
        # Check description
        if reviewed_item.get("description") != original_item.get("description"):
            changes.append("description")
            reviewed_item["old_description"] = original_item.get("description")
        
        # Check owner
        reviewed_owner = reviewed_item.get("owner", {})
        original_owner = original_item.get("owner", {})
        if isinstance(reviewed_owner, dict) and isinstance(original_owner, dict):
            if (reviewed_owner.get("name") != original_owner.get("name") or 
                reviewed_owner.get("email") != original_owner.get("email")):
                changes.append("owner")
                reviewed_item["old_owner"] = original_owner
        elif reviewed_owner != original_owner:
            changes.append("owner")
            reviewed_item["old_owner"] = original_owner
        
        # Check due date
        if reviewed_item.get("due_date") != original_item.get("due_date"):
            changes.append("due_date")
            reviewed_item["old_due_date"] = original_item.get("due_date")
        
        # Check priority
        if reviewed_item.get("priority") != original_item.get("priority"):
            changes.append("priority")
            reviewed_item["old_priority"] = original_item.get("priority")
        
        # Check status
        if reviewed_item.get("status") != original_item.get("status"):
            changes.append("status")
            reviewed_item["old_status"] = original_item.get("status")
        
        # Check tags
        reviewed_tags = set(reviewed_item.get("tags", []))
        original_tags = set(original_item.get("tags", []))
        if reviewed_tags != original_tags:
            changes.append("tags")
            reviewed_item["old_tags"] = list(original_tags)
        
        # Add change tracking
        if changes:
            reviewed_item["change_type"] = "modified"
            reviewed_item["fields_changed"] = changes
            print(f"[DEBUG] Item {idx}: Modified fields: {', '.join(changes)}")
        else:
            reviewed_item["change_type"] = "unchanged"
    
    return reviewed_list



# =====================================================
# EXTRACTED FUNCTION - Update MoM with Reviewed Items
# =====================================================

def update_mom_with_reviewed_items(output_dir: str = "outputs", 
                                    model: str = "openai/gpt-4o-mini",
                                    temperature: float = 0.2):
    """
    Function to merge reviewed action items with MoM and extract final items.
    This function can be called from multiple API endpoints.
    
    Args:
        output_dir: Output directory containing MoM and action items
        model: LLM model to use for crewAgent3
        temperature: Temperature setting for LLM
        
    Returns:
        dict: Contains updated_mom_content, action_items, and metadata
        
    Raises:
        FileNotFoundError: If required files don't exist
        Exception: For other processing errors
    """
    print(f"[DEBUG] update_mom_with_reviewed_items: Starting...")
    
    mom_path = os.path.join(output_dir, "minutes_of_meeting.md")
    action_items_path = os.path.join(output_dir, "action_items.json")
    
    # Validate input files exist
    if not os.path.exists(mom_path):
        print(f"[DEBUG] MoM file not found: {mom_path}")
        raise FileNotFoundError(f"minutes_of_meeting.md not found at {mom_path}")
    
    if not os.path.exists(action_items_path):
        print(f"[DEBUG] Action items file not found: {action_items_path}")
        raise FileNotFoundError(f"action_items.json not found at {action_items_path}")
    
    print(f"[DEBUG] Input files validated")
    print(f"[DEBUG]   MoM path: {mom_path}")
    print(f"[DEBUG]   Action items path: {action_items_path}")
    
    # Import and run crewAgent3
    print(f"[DEBUG] Running crewAgent3 to merge action items...")
    from crewAgent3 import main as crewAgent3_main
    
    # Run crewAgent3 with no-backup option
    crewAgent3_main(
        mom_path=mom_path,
        action_items_path=action_items_path,
        out_dir=output_dir,
        model=model,
        temperature=temperature,
        backup=False
    )
    
    print(f"[DEBUG] crewAgent3 execution completed")
    
    # Check if updated MoM was created
    if not os.path.exists(mom_path):
        print(f"[DEBUG] Updated MoM not created: {mom_path}")
        raise FileNotFoundError("Failed to create updated MoM")
    
    # Read the updated MoM content
    print(f"[DEBUG] Reading updated MoM from {mom_path}")
    with open(mom_path, 'r', encoding='utf-8') as f:
        updated_mom_content = f.read()
    
    print(f"[DEBUG] Updated MoM read successfully, size: {len(updated_mom_content)} chars")
    
    # Read the reviewed action items to return them
    with open(action_items_path, 'r', encoding='utf-8') as f:
        reviewed_action_items = json.load(f)
    
    # Prepare response data
    response_data = {
        "status": "success",
        "message": "MoM updated successfully with reviewed action items",
        "updated_mom_content": updated_mom_content,
        "action_items": reviewed_action_items.get("action_items", []),
        "total_action_items": reviewed_action_items.get("total_items", 0),
        "meeting_date": reviewed_action_items.get("meeting_date", "Unknown"),
        "updated_at": datetime.now().isoformat()
    }
    
    print(f"[DEBUG] Returning response with {response_data['total_action_items']} action items")
    return response_data


# =====================================================
# API ENDPOINTS
# =====================================================

@app.post("/api/review_and_assign_action_items")
def review_and_assign_action_items(reviewed_items: dict):
    """
    API endpoint to receive reviewed action items from frontend.
    Saves reviewed items to action_items.json and updates MoM.
    
    Request body example:
    {
        "action_items": [
            {
                "id": "action_001",
                "description": "Updated description",
                "owner": {"name": "John Doe", "email": "john@example.com"},
                "due_date": "Friday",
                "priority": "high",
                "status": "pending",
                "tags": []
            }
        ],
        "meeting_date": "November 1, 2025",
        "total_items": 3
    }
    
    Returns:
        JSONResponse with updated MoM content and final action items
    """
    print("[DEBUG] === Starting review_and_assign_action_items API ===")
    
    try:
        reviewed_items_obj = json.loads(reviewed_items) if isinstance(reviewed_items, str) else reviewed_items
        # Extract data from request
        action_items = reviewed_items_obj.get("action_items", [])
        meeting_date = reviewed_items_obj.get("meeting_date", "Unknown")
        total_items = reviewed_items_obj.get("total_items", len(action_items))
        
        print(f"[DEBUG] Received {total_items} reviewed action items")
        print(f"[DEBUG] Meeting date: {meeting_date}")
        
        # Save reviewed action items to file
        output_dir = "outputs"
        action_items_path = os.path.join(output_dir, "action_items.json")
        
        reviewed_data = {
            "meeting_date": meeting_date,
            "total_items": total_items,
            "action_items": action_items,
            "generated_at": datetime.now().isoformat()
        }
        
        print(f"[DEBUG] Saving reviewed action items to {action_items_path}")
        with open(action_items_path, 'w', encoding='utf-8') as f:
            json.dump(reviewed_data, f, indent=2, ensure_ascii=False)
        
        print(f"[DEBUG] Reviewed action items saved successfully")
        
        # Call the function to update MoM with reviewed items
        print(f"[DEBUG] Calling update_mom_with_reviewed_items function...")
        update_response = update_mom_with_reviewed_items(
            output_dir=output_dir,
            model="openai/gpt-4o-mini",
            temperature=0.2
        )
        
        print(f"[DEBUG] MoM updated successfully")
        print(f"[DEBUG] Total action items in response: {update_response['total_action_items']}")
        
        # Return the response
        return JSONResponse(content=update_response)
        
    except FileNotFoundError as e:
        print(f"[DEBUG] File not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"[DEBUG] === ERROR in review_and_assign_action_items ===")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

def update_meet_data(email_sent: bool = False):
    """Updated function with debugging and fixes"""
    print("\n" + "="*60)
    print("DEBUGGING: update_meet_data()")
    print("="*60)
    # Check current working directory
    print(f"\nCurrent working directory: {os.getcwd()}")
    # Read meetings
    print("\n1. Reading meet_data.json...")
    meet_data = read_meetings_from_json(filename="meet_data.json")
    print(f"   ✓ Read {len(meet_data)} meetings")
    # Find max meeting
    print("\n2. Finding max meeting...")
    max_meeting = max(meet_data, key=lambda x: int(x['id']))
    print(f"   ✓ Found max meeting with ID: {max_meeting['id']}")
    print(f"   Title: {max_meeting['title']}")
    # Create copy and remove
    print("\n3. Creating copy and removing max meeting...")
    new_meet_data = deepcopy(meet_data)
    print(f"   Before remove: {len(new_meet_data)} meetings")
    new_meet_data.remove(max_meeting)
    print(f"   After remove: {len(new_meet_data)} meetings")
    # Load additional data
    output_dir = "outputs"
    print("\n4. Loading additional data...")
    max_meeting['emailSent'] = email_sent
    print(f"   ✓ Set emailSent to {email_sent}")
    # Load reviewed transcripts
    reviewed_transcript_file_path = os.path.join(output_dir, "reviewed_transcripts.json")
    print(f"   Loading: {reviewed_transcript_file_path}")
    if os.path.exists(reviewed_transcript_file_path):
        with open(reviewed_transcript_file_path, encoding="utf-8") as f:
            reviewed_classification_data = json.load(f)
        max_meeting['reviewed_classification_data'] = reviewed_classification_data['transcripts']
        print(f"   ✓ Loaded reviewed transcripts")
    else:
        print(f"   ⚠ File not found: {reviewed_transcript_file_path}")
    # Load MoM
    MoM_file_path = os.path.join(output_dir, "minutes_of_meeting.md")
    print(f"   Loading: {MoM_file_path}")
    if os.path.exists(MoM_file_path):
        with open(MoM_file_path, encoding="utf-8") as f:
            MoM_content = f.read()
        max_meeting['MoM_content'] = MoM_content
        print(f"   ✓ Loaded MoM (length: {len(MoM_content)} chars)")
    else:
        print(f"   ⚠ File not found: {MoM_file_path}")
    # Load action items
    action_items_file_path = os.path.join(output_dir, "action_items.json")
    print(f"   Loading: {action_items_file_path}")
    if os.path.exists(action_items_file_path):
        with open(action_items_file_path, encoding="utf-8") as f:
            action_items_data = json.load(f)
        max_meeting['action_items'] = action_items_data.get("action_items", [])
        print(f"   ✓ Loaded {len(max_meeting['action_items'])} action items")
    else:
        print(f"   ⚠ File not found: {action_items_file_path}")
    
    print("\n5. Modified max_meeting:")
    print(f"   Keys: {list(max_meeting.keys())}")
    # Append back
    print("\n6. Appending modified meeting back to list...")
    new_meet_data.append(max_meeting)
    print(f"   ✓ List now has {len(new_meet_data)} meetings")
    # Write to file
    print("\n7. Writing to meet_data.json...")
    output_file = "meet_data.json"
    output_path = os.path.abspath(output_file)
    print(f"   Full path: {output_path}")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(new_meet_data, f, indent=2, ensure_ascii=False)
        print(f"   ✓ File written successfully")
        # Verify file size
        file_size = os.path.getsize(output_file)
        print(f"   File size: {file_size} bytes")
    except Exception as e:
        print(f"   ❌ ERROR writing file: {e}")
        raise
    # Verify by reading back
    print("\n8. Verifying by reading back...")
    with open(output_file, 'r', encoding='utf-8') as f:
        verify_data = json.load(f)
    print(f"   ✓ File contains {len(verify_data)} meetings")
    
    # Check if max_meeting is in the file with new fields
    max_meeting_in_file = next((m for m in verify_data if m['id'] == max_meeting['id']), None)
    if max_meeting_in_file:
        print(f"   ✓ Max meeting found in file")
        print(f"   Keys in file: {list(max_meeting_in_file.keys())}")
        if 'MoM_content' in max_meeting_in_file:
            print(f"   ✓ MoM_content is present in file")
        if 'action_items' in max_meeting_in_file:
            print(f"   ✓ action_items is present in file")
    else:
        print(f"   ❌ Max meeting NOT found in file!")
    
    print("\n" + "="*60)
    print("✓ Update completed successfully!")
    print("="*60)
    
    return new_meet_data

@app.post("/api/review_and_finalize_mom")
def review_and_finalize_mom(finalized_data: dict):
    """
    API endpoint to receive and save the finalized MoM from frontend.
    
    Request body:
    {
        "mom_content": "# Minutes of Meeting...",
        "action_items": [ ... ]
    }
    
    Returns:
    {
        "status": "success",
        "message": "MoM finalized and saved successfully",
        "file_path": "outputs/minutes_of_meeting.md",
        "file_size": 2682,
        "action_items": [ ... ],
        "saved_at": "2025-11-03T..."
    }
    """
    print("[DEBUG] === Starting review_and_finalize_mom API ===")
    
    try:
        # Extract data from request
        mom_content = finalized_data.get("mom_content", "")
        action_items = finalized_data.get("action_items", [])
        print(f"[DEBUG] Received finalized MoM content and {len(action_items)} action items")

        if not mom_content:
            print(f"[DEBUG] No MoM content provided")
            raise HTTPException(status_code=400, detail="mom_content is required")
        
        print(f"[DEBUG] MoM content length: {len(mom_content)} characters")
        
        # Save the finalized MoM to file
        output_dir = "outputs"
        mom_path = os.path.join(output_dir, "minutes_of_meeting.md")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"[DEBUG] Saving finalized MoM to {mom_path}")
        with open(mom_path, 'w', encoding='utf-8') as f:
            f.write(mom_content)
        
        # Get file size
        file_size = os.path.getsize(mom_path)
        saved_at = datetime.now().isoformat()
        
        print(f"[DEBUG] MoM saved successfully, size: {file_size} bytes")
        # Send slack notification or email if needed
        try:
            slack_notify()
            print(f"[DEBUG] Slack notification sent successfully")
            emailSent = True
        except Exception as e:
            print(f"[DEBUG] Error sending Slack notification: {e}")
            emailSent = False

        # Update meet_data.json with finalized MoM and reviewed classification data
        print(f"[DEBUG] Updating meet_data.json with finalized MoM and reviewed data...")
        update_meet_data(email_sent=emailSent)
        print(f"[DEBUG] meet_data.json updated successfully")


        # Return success response
        response = {
            "status": "success",
            "message": "MoM finalized and saved successfully",
            "action_items" : action_items,
            "file_path": mom_path,
            "file_size": file_size,
            "saved_at": saved_at
        }
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] === ERROR in review_and_finalize_mom ===")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error finalizing MoM: {str(e)}")


# @app.post("/api/update_mom")
# def update_mom():
#     """
#     Standalone API to merge reviewed action items with MoM.
#     Now calls the extracted update_mom_with_reviewed_items function.
#     """
#     print("[DEBUG] === Starting update_mom API ===")
#     
#     try:
#         # Call the extracted function
#         update_response = update_mom_with_reviewed_items(
#             output_dir="outputs",
#             model="openai/gpt-4o-mini",
#             temperature=0.2
#         )
#         
#         return JSONResponse(content=update_response)
#         
#     except FileNotFoundError as e:
#         print(f"[DEBUG] File not found: {e}")
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         print(f"[DEBUG] === ERROR in update_mom ===")
#         print(f"[DEBUG] Error type: {type(e).__name__}")
#         print(f"[DEBUG] Error message: {str(e)}")
#         import traceback
#         print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
#         raise HTTPException(status_code=500, detail=f"Error updating MoM: {str(e)}")


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