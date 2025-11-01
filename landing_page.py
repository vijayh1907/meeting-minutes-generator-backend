import os
import json
import time
from crewAgent1 import main as crewAgent1_main
from crewAgent2 import main as crewAgent2_main
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


@app.post("/api/create_mom_and_action_items")
async def create_mom_and_action_items(
    meeting_id: str = Form(None),
    output_format: str = Form("markdown")  # Options: markdown, json, both
):
    """
    Generate Minutes of Meeting (MoM) and Action Items from reviewed transcripts.
    
    Args:
        meeting_id: Optional meeting ID for reference (uses next_id if not provided)
        output_format: Output format - 'markdown' (default), 'json', or 'both'
    
    Returns:
        JSON response with paths to generated files and action items summary
    """
    global next_id
    
    print(f"[DEBUG] === Starting create_mom_and_action_items ===")
    print(f"[DEBUG] Received parameters:")
    print(f"[DEBUG]   - meeting_id: {meeting_id or next_id}")
    print(f"[DEBUG]   - output_format: {output_format}")
    
    try:
        # Use provided meeting_id or fall back to next_id
        current_meeting_id = meeting_id or next_id
        if not current_meeting_id:
            print(f"[DEBUG] ERROR: No meeting_id available")
            raise HTTPException(status_code=400, detail="Meeting ID not found. Please upload meeting files first.")
        
        # Define paths
        input_file = "outputs/reviewed_transcripts.json"
        output_dir = "outputs"
        model = "openai/gpt-4o-mini"
        temperature = 0.2
        
        print(f"[DEBUG] Configuration:")
        print(f"[DEBUG]   - input_file: {input_file}")
        print(f"[DEBUG]   - output_dir: {output_dir}")
        print(f"[DEBUG]   - model: {model}")
        print(f"[DEBUG]   - temperature: {temperature}")
        
        # Check if input file exists
        if not os.path.exists(input_file):
            print(f"[DEBUG] ERROR: Input file not found: {input_file}")
            raise HTTPException(
                status_code=404, 
                detail=f"Reviewed transcripts file not found. Please review the content first."
            )
        
        print(f"[DEBUG] Input file found: {input_file}")
        print(f"[DEBUG] Starting MoM generation with crewAgent2...")
        
        # Call crewAgent2.main to generate MoM and action items
        try:
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
            print(f"[DEBUG] MoM generation completed successfully")
            print(f"[DEBUG] Process execution time: {minutes} min {seconds} sec")
        except Exception as e:
            print(f"[DEBUG] Error in MoM generation: {e}")
            print(f"[DEBUG] Error type: {type(e).__name__}")
            import traceback
            print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error generating MoM: {str(e)}")
        
        # Prepare response with file paths
        response_data = {
            "meeting_id": current_meeting_id,
            "status": "success",
            "message": "Minutes of Meeting and Action Items generated successfully",
            "execution_time": f"{minutes} min {seconds} sec",
            "files_generated": []
        }
        
        # Check for generated files and add to response
        mom_md_path = os.path.join(output_dir, "minutes_of_meeting.md")
        mom_json_path = os.path.join(output_dir, "minutes_of_meeting.json")
        action_items_path = os.path.join(output_dir, "action_items.json")
        
        if os.path.exists(mom_md_path):
            print(f"[DEBUG] Found: {mom_md_path}")
            response_data["files_generated"].append({
                "type": "minutes_markdown",
                "path": mom_md_path,
                "size": os.path.getsize(mom_md_path)
            })
        
        if os.path.exists(mom_json_path):
            print(f"[DEBUG] Found: {mom_json_path}")
            response_data["files_generated"].append({
                "type": "minutes_json",
                "path": mom_json_path,
                "size": os.path.getsize(mom_json_path)
            })
        
        # Read and include action items in response
        if os.path.exists(action_items_path):
            print(f"[DEBUG] Found: {action_items_path}")
            try:
                with open(action_items_path, 'r', encoding='utf-8') as f:
                    action_items_data = json.load(f)
                
                response_data["files_generated"].append({
                    "type": "action_items_json",
                    "path": action_items_path,
                    "size": os.path.getsize(action_items_path)
                })
                
                response_data["action_items"] = action_items_data
                response_data["action_items_count"] = action_items_data.get("total_items", 0)
                
                print(f"[DEBUG] Action items loaded: {response_data['action_items_count']} items")
            except Exception as e:
                print(f"[DEBUG] Error reading action items: {e}")
                response_data["action_items_error"] = str(e)
        
        # Read MoM content to include in response (optional, for preview)
        if os.path.exists(mom_md_path):
            try:
                with open(mom_md_path, 'r', encoding='utf-8') as f:
                    mom_content = f.read()
                response_data["mom_preview"] = mom_content[:500] + "..." if len(mom_content) > 500 else mom_content
            except Exception as e:
                print(f"[DEBUG] Error reading MoM preview: {e}")
        
        print(f"[DEBUG] === MoM generation completed successfully ===")
        print(f"[DEBUG] Generated {len(response_data['files_generated'])} files")
        
        return JSONResponse(content=response_data)
        
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


@app.post("/api/review_and_assign_action_items")
async def review_and_assign_action_items(
    action_items_reviewed: str = Form(...)  # JSON string, parse in backend
):
    """
    Review and assign action items after MoM generation.
    Allows users to modify action item details (owner, due date, priority, etc.)
    before finalizing them.
    
    Args:
        action_items_reviewed: JSON string containing reviewed action items
        
    Returns:
        The reviewed and updated action items
    """
    global next_id
    
    print(f"[DEBUG] === Starting review_and_assign_action_items ===")
    
    try:
        # Parse the JSON string
        print(f"[DEBUG] Parsing action_items_reviewed JSON...")
        try:
            action_items_reviewed = json.loads(action_items_reviewed)
            print(f"[DEBUG] Successfully parsed action items")
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON decode error: {e}")
            raise HTTPException(status_code=422, detail=f"Invalid JSON format: {str(e)}")
        
        # Get the original action items for comparison
        output_dir = "outputs"
        original_path = os.path.join(output_dir, "action_items.json")
        
        if os.path.exists(original_path):
            print(f"[DEBUG] Loading original action items from {original_path}")
            try:
                with open(original_path, 'r', encoding='utf-8') as f:
                    original_data = json.load(f)
                print(f"[DEBUG] Original action items loaded successfully")
            except Exception as e:
                print(f"[DEBUG] Warning: Could not load original action items: {e}")
                original_data = None
        else:
            print(f"[DEBUG] No original action items file found")
            original_data = None
        
        # Process and flag changes
        result = compare_and_flag_action_item_changes(action_items_reviewed, original_data)
        
        # Create the updated structure
        updated_action_items = {
            "meeting_id": next_id,
            "reviewed_at": __import__('datetime').datetime.now().isoformat(),
            "total_items": len(result) if isinstance(result, list) else result.get("total_items", 0),
            "action_items": result if isinstance(result, list) else result.get("action_items", [])
        }
        
        # If the original data had additional metadata, preserve it
        if original_data and isinstance(original_data, dict):
            if "meeting_date" in original_data:
                updated_action_items["meeting_date"] = original_data["meeting_date"]
            if "generated_at" in original_data:
                updated_action_items["generated_at"] = original_data["generated_at"]
        
        # Save to reviewed_action_items.json
        reviewed_path = os.path.join(output_dir, "reviewed_action_items.json")
        print(f"[DEBUG] Saving reviewed action items to {reviewed_path}")
        
        with open(reviewed_path, "w", encoding="utf-8") as f:
            json.dump(updated_action_items, f, indent=2, ensure_ascii=False)
        
        print(f"[DEBUG] Reviewed action items saved successfully")
        print(f"[DEBUG] Total items: {updated_action_items['total_items']}")
        
        # Return the action items array for display
        return JSONResponse(content=updated_action_items["action_items"])
        
    except HTTPException:
        print(f"[DEBUG] Re-raising HTTP exception")
        raise
    except Exception as e:
        print(f"[DEBUG] === UNEXPECTED ERROR ===")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


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