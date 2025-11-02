# crewAgent3.py
import os
import json
import re
from dotenv import load_dotenv
from pathlib import Path
from crewai import Crew, Process
from datetime import datetime

# Import the custom modules
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tools.mom_and_action_items_reader_tool import MomAndActionItemsReaderTool
from agents.mom_merger_agent import build_mom_merger_agent
from tasks.mom_merge_task import build_mom_merge_task

def extract_action_items_from_mom(mom_content: str, meeting_date: str) -> dict:
    """
    Extract action items from the updated MoM content.
    
    Args:
        mom_content: The markdown content of the updated MoM
        meeting_date: The meeting date
        
    Returns:
        Dictionary with action_items structure
    """
    # Remove markdown code block markers if present
    content = mom_content.strip()
    if content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]
    content = content.strip()
    
    # Extract action items section
    lines = content.split('\n')
    action_items = []
    in_action_section = False
    
    for line in lines:
        # Check if we're entering the Action Items section
        if '## Action Items' in line or '### Action Items' in line:
            in_action_section = True
            continue
        
        # Check if we're leaving the Action Items section
        if in_action_section and (line.startswith('## ') or line.startswith('### ')):
            break
        
        # Collect action item lines
        if in_action_section and line.strip().startswith('-') and '**' in line:
            action_items.append(line)
    
    # Parse each action item
    parsed_items = []
    for idx, line in enumerate(action_items, start=1):
        item = parse_action_item_line(line, idx, meeting_date)
        parsed_items.append(item)
    
    return {
        "meeting_date": meeting_date,
        "generated_at": datetime.now().isoformat(),
        "total_items": len(parsed_items),
        "action_items": parsed_items
    }

def parse_action_item_line(line: str, idx: int, meeting_date: str) -> dict:
    """
    Parse a single action item line from markdown format.
    
    Expected format:
    - **[Description]** - Owner: [Name] ([Email]) - Due: [Date] - Priority: [Priority] - Status: [Status]
    """
    # Remove leading bullet and whitespace
    line = line.strip().lstrip('-').strip()
    
    # Initialize result
    result = {
        "id": f"action_{idx:03d}",
        "description": "",
        "owner": {
            "name": "Not specified",
            "email": None
        },
        "due_date": "Not specified",
        "due_date_calculated": None,
        "status": "pending",
        "created_from_meeting": meeting_date,
        "priority": "medium",
        "tags": []
    }
    
    # Extract description (text between ** and first " - Owner:")
    desc_match = re.search(r'\*\*(.*?)\*\*\s*-\s*Owner:', line, re.IGNORECASE)
    if desc_match:
        result["description"] = desc_match.group(1).strip()
    
    # Extract owner name and email
    owner_match = re.search(r'Owner:\s*([^(]+?)(?:\s*\(([^)]+)\))?\s*-\s*Due:', line, re.IGNORECASE)
    if owner_match:
        name = owner_match.group(1).strip()
        email = owner_match.group(2).strip() if owner_match.group(2) else None
        
        if name and name.lower() != "not specified":
            result["owner"]["name"] = name
            result["owner"]["email"] = email
    
    # Extract due date - FIXED: Use .+? instead of [^-]+? to handle dates with dashes
    due_match = re.search(r'Due:\s*(.+?)\s*-\s*Priority:', line, re.IGNORECASE)
    if due_match:
        due_date = due_match.group(1).strip()
        if due_date and due_date.lower() != "not specified":
            result["due_date"] = due_date
            
            # Extract calculated date if present (format: Day, (DD-MM-YYYY))
            calc_date_match = re.search(r'\((\d{2}-\d{2}-\d{4})\)', due_date)
            if calc_date_match:
                result["due_date_calculated"] = calc_date_match.group(1)
    
    # Extract priority
    priority_match = re.search(r'Priority:\s*(\w+)\s*-\s*Status:', line, re.IGNORECASE)
    if priority_match:
        priority = priority_match.group(1).strip().lower()
        if priority in ['high', 'medium', 'low']:
            result["priority"] = priority
    
    # Extract status
    status_match = re.search(r'Status:\s*(.+?)(?:\s*$)', line, re.IGNORECASE)
    if status_match:
        status = status_match.group(1).strip()
        # Convert from "In Progress" to "in_progress", "Pending" to "pending", etc.
        status_normalized = status.lower().replace(' ', '_')
        result["status"] = status_normalized
    
    return result

def extract_meeting_date(content: str) -> str:
    """Extract meeting date from MoM content."""
    # Remove code blocks
    content = content.strip()
    if content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]
    
    # Look for **Date:** line
    date_match = re.search(r'\*\*Date:\*\*\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
    if date_match:
        return date_match.group(1).strip()
    
    return "Not specified"

def main(mom_path: str = "outputs/minutes_of_meeting.md",
         action_items_path: str = "outputs/action_items.json",
         out_dir: str = "outputs",
         model: str = "openai/gpt-4o-mini",
         temperature: float = 0.2,
         backup: bool = True):
    """
    Merge reviewed action items with Minutes of Meeting using CrewAI,
    then extract and save updated action items.
    
    Args:
        mom_path: Path to the original MoM markdown file
        action_items_path: Path to action_items.json
        out_dir: Output directory for the updated MoM and action items
        model: LLM model to use
        temperature: Temperature for LLM (lower = more precise)
        backup: Whether to create a backup of the original MoM
    """
    load_dotenv()
    
    print("=" * 70)
    print("MoM Action Items Merger - crewAgent3.py (CrewAI)")
    print("=" * 70)
    print()
    
    # Validate input files
    mom_file = Path(mom_path)
    action_items_file = Path(action_items_path)
    
    if not mom_file.exists():
        print(f"ERROR: MoM file not found: {mom_file.absolute()}")
        return None
    
    if not action_items_file.exists():
        print(f"ERROR: Action items file not found: {action_items_file.absolute()}")
        return None
    
    print(f"Found MoM file: {mom_file.absolute()}")
    print(f"   File size: {mom_file.stat().st_size / 1024:.2f} KB")
    print()
    print(f"Found reviewed action items: {action_items_file.absolute()}")
    print(f"   File size: {action_items_file.stat().st_size / 1024:.2f} KB")
    print()
    
    # Create backup if requested
    if backup:
        backup_path = mom_file.parent / f"{mom_file.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{mom_file.suffix}"
        import shutil
        shutil.copy2(mom_file, backup_path)
        print(f"Created backup: {backup_path.name}")
        print()
    
    # 1) Tool
    reader_tool = MomAndActionItemsReaderTool()
    
    # 2) Agent
    agent = build_mom_merger_agent(model=model, temperature=temperature, tools=[reader_tool])
    
    # 3) Task (use absolute paths for reliability)
    absolute_mom_path = str(mom_file.absolute())
    absolute_action_items_path = str(action_items_file.absolute())
    task = build_mom_merge_task(absolute_mom_path, absolute_action_items_path, agent)
    
    # 4) Crew & kickoff
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True
    )
    
    print(f"Starting MoM merge process...")
    print(f"Using model: {model} with temperature: {temperature}")
    print("This may take 30-60 seconds...")
    print()
    
    result = crew.kickoff()
    
    # 5) Save output
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Get the raw output
    if result.tasks_output:
        merged_content = result.tasks_output[0].raw
    else:
        merged_content = result.raw
    
    # Save the merged MoM as minutes_of_meeting.md
    output_file = out_dir / "minutes_of_meeting.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(merged_content)
    
    print()
    print("=" * 70)
    print("Extracting Action Items from Updated MoM...")
    print("=" * 70)
    
    # 6) Extract action items from the updated MoM
    meeting_date = extract_meeting_date(merged_content)
    action_items_data = extract_action_items_from_mom(merged_content, meeting_date)
    
    # Save the extracted action items
    action_items_output = out_dir / "action_items.json"
    with open(action_items_output, "w", encoding="utf-8") as f:
        json.dump(action_items_data, f, indent=2, ensure_ascii=False)
    
    print(f"Extracted {action_items_data['total_items']} action items")
    print()
    
    print("=" * 70)
    print("Update Complete!")
    print("=" * 70)
    print(f"Updated MoM saved: {output_file.absolute()}")
    print(f"   File size: {output_file.stat().st_size / 1024:.2f} KB")
    print(f"Action items saved: {action_items_output.absolute()}")
    print(f"   Total items: {action_items_data['total_items']}")
    print(f"Original MoM preserved: {mom_file.name}")
    if backup:
        print(f"Backup also created: {backup_path.name}")
    print()
    
    # Return the data structure for API use
    return {
        "status": "success",
        "message": "MoM updated successfully with reviewed action items",
        "updated_mom_content": merged_content,
        "action_items": action_items_data["action_items"],
        "total_action_items": action_items_data["total_items"],
        "updated_at": datetime.now().isoformat(),
        "files": {
            "updated_mom": str(output_file.absolute()),
            "action_items_json": str(action_items_output.absolute())
        }
    }

if __name__ == "__main__":
    import argparse
    
    ap = argparse.ArgumentParser(
        description="Merge reviewed action items with Minutes of Meeting using CrewAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (updates outputs/minutes_of_meeting.md in place with backup)
  python crewAgent3.py
  
  # Specify custom paths
  python crewAgent3.py --mom outputs/minutes_of_meeting.md --items outputs/action_items.json
  
  # Use different model
  python crewAgent3.py --model openai/gpt-4o
  
  # Disable backup
  python crewAgent3.py --no-backup
        """
    )
    
    ap.add_argument(
        "--mom",
        default="outputs/minutes_of_meeting.md",
        help="Path to the original MoM markdown file (default: outputs/minutes_of_meeting.md)"
    )
    
    ap.add_argument(
        "--items",
        default="outputs/action_items.json",
        help="Path to action_items.json (default: outputs/action_items.json)"
    )
    
    ap.add_argument(
        "--out",
        default="outputs",
        help="Output directory (default: outputs)"
    )
    
    ap.add_argument(
        "--model",
        default="openai/gpt-4o-mini",
        help="LLM model to use (default: openai/gpt-4o-mini)"
    )
    
    ap.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Temperature for LLM (default: 0.2)"
    )
    
    ap.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create a backup of the original MoM"
    )
    
    args = ap.parse_args()
    
    main(
        mom_path=args.mom,
        action_items_path=args.items,
        out_dir=args.out,
        model=args.model,
        temperature=args.temperature,
        backup=not args.no_backup
    )

# python crewAgent3.py --mom outputs/minutes_of_meeting.md --items outputs/action_items.json --no-backup