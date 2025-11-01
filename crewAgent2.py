# crewAgent2.py
import os
import json
import re
from dotenv import load_dotenv
from pathlib import Path
from crewai import Crew, Process

from src.tools.reviewed_transcript_reader_tool import ReviewedTranscriptReaderTool
from src.agents.mom_generator_agent import build_mom_generator_agent
from src.tasks.mom_generation_task import build_mom_generation_task
from src.io_utils import save_json

def extract_action_items_from_mom(mom_content: str, meeting_date: str = None) -> list:
    """
    Extract action items from the generated MoM markdown.
    
    Args:
        mom_content: The markdown content of the MoM
        meeting_date: Meeting date for reference
        
    Returns:
        List of action item dictionaries
    """
    action_items = []
    in_action_section = False
    
    for line in mom_content.split('\n'):
        # Detect action items section
        if '### Action Items' in line or '## Action Items' in line:
            in_action_section = True
            continue
        
        # Exit action items section
        if in_action_section and (line.startswith('###') or line.startswith('##')) and 'Action Items' not in line:
            break
        
        # Parse action item line
        if in_action_section and line.strip().startswith('-'):
            # Expected format: - **Description** - Owner: Name (email) - Due: Date
            
            # Extract description
            desc_match = re.search(r'\*\*(.+?)\*\*', line)
            if not desc_match:
                continue
            description = desc_match.group(1).strip()
            
            # Extract owner
            owner_match = re.search(r'Owner:\s*([^-]+?)(?:\s*\(([^)]+)\))?(?:\s*-|$)', line)
            owner_name = "Not specified"
            owner_email = None
            if owner_match:
                owner_name = owner_match.group(1).strip()
                owner_email = owner_match.group(2).strip() if owner_match.group(2) else None
            
            # Extract due date
            due_match = re.search(r'Due:\s*(.+?)$', line)
            due_date = "Not specified"
            due_date_calculated = None
            if due_match:
                due_date = due_match.group(1).strip()
                # Extract calculated date if present
                date_calc_match = re.search(r'\((\d{2}-\d{2}-\d{4})\)', due_date)
                if date_calc_match:
                    due_date_calculated = date_calc_match.group(1)
            
            action_items.append({
                "id": f"action_{len(action_items) + 1:03d}",
                "description": description,
                "owner": {
                    "name": owner_name,
                    "email": owner_email
                },
                "due_date": due_date,
                "due_date_calculated": due_date_calculated,
                "status": "pending",
                "created_from_meeting": meeting_date,
                "priority": "medium",  # Default, can be customized
                "tags": []  # Can be extracted from description if needed
            })
    
    return action_items

def main(in_path: str = "outputs/reviewed_transcripts.json", 
         out_dir: str | Path = "outputs",
         model: str = "openai/gpt-4o-mini", 
         temperature: float = 0.2,
         output_format: str = "markdown"):
    """
    Generate Minutes of Meeting (MoM) from reviewed transcripts.
    
    Args:
        in_path: Path to reviewed_transcripts.json (default: outputs/reviewed_transcripts.json)
        out_dir: Output directory for generated MoM
        model: LLM model to use
        temperature: Temperature for LLM
        output_format: Output format (markdown, json, or both)
    """
    load_dotenv()
    
    # Validate input file exists
    input_file = Path(in_path)
    if not input_file.exists():
        print(f"❌ ERROR: Input file not found: {input_file.absolute()}")
        print(f"   Looking for: {in_path}")
        print(f"   Current directory: {Path.cwd()}")
        print()
        print("💡 Tip: By default, the script looks for 'outputs/reviewed_transcripts.json'")
        print("   Make sure you've run crewAgent1.py first to generate this file.")
        return
    
    if not input_file.is_file():
        print(f"❌ ERROR: Path is not a file: {input_file.absolute()}")
        return
    
    if input_file.suffix.lower() != '.json':
        print(f"⚠️  WARNING: Expected .json file, got: {input_file.suffix}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    print(f"✅ Found input file: {input_file.absolute()}")
    print(f"   File size: {input_file.stat().st_size / 1024:.2f} KB")
    print()

    # Extract meeting date for action items
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        transcripts = data.get('transcripts', [])
        meeting_date = None
        for item in transcripts[:15]:
            if 'date' in item.get('tags', []):
                meeting_date = item.get('raw_transcript_line', '').replace('**Date:**', '').strip()
                break
    except:
        meeting_date = None

    # 1) Tools
    reader_tool = ReviewedTranscriptReaderTool()

    # 2) Agent
    agent = build_mom_generator_agent(model=model, temperature=temperature, tools=[reader_tool])

    # 3) Task (use absolute path for reliability)
    absolute_path = str(input_file.absolute())
    task = build_mom_generation_task(absolute_path, agent, output_format=output_format)

    # 4) Crew & kickoff
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True  # Enable verbose to see what's happening
    )
    
    print(f"🚀 Generating Minutes of Meeting from {in_path}...")
    print(f"📋 Using model: {model} with temperature: {temperature}")
    print(f"📝 Output format: {output_format}")
    print("⏳ This may take 30-60 seconds...\n")
    
    result = crew.kickoff()

    # 5) Parse and save output
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Get the raw output
    if result.tasks_output:
        mom_content = result.tasks_output[0].raw
    else:
        mom_content = result.raw

    # Save based on format
    if output_format in ["markdown", "both"]:
        md_path = out_dir / "minutes_of_meeting.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(mom_content)
        print(f"✅ Saved Markdown MoM: {md_path.resolve()}")
        
        # Extract and save action items as JSON
        action_items = extract_action_items_from_mom(mom_content, meeting_date)
        if action_items:
            action_items_data = {
                "meeting_date": meeting_date,
                "generated_at": __import__('datetime').datetime.now().isoformat(),
                "total_items": len(action_items),
                "action_items": action_items
            }
            action_items_path = out_dir / "action_items.json"
            with open(action_items_path, "w", encoding="utf-8") as f:
                json.dump(action_items_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved Action Items JSON: {action_items_path.resolve()}")
            print(f"   Found {len(action_items)} action items")

    if output_format in ["json", "both"]:
        # Try to parse as JSON if it's in JSON format
        try:
            if isinstance(mom_content, str):
                # Remove code fences if present
                cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", mom_content, flags=re.IGNORECASE).strip()
                mom_json = json.loads(cleaned)
            else:
                mom_json = mom_content
            
            json_path = save_json(mom_json, out_dir / "minutes_of_meeting.json")
            print(f"✅ Saved JSON MoM: {json_path.resolve()}")
        except json.JSONDecodeError:
            print("⚠️  Could not parse output as JSON. Saving as text instead.")
            txt_path = out_dir / "minutes_of_meeting.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(mom_content)
            print(f"✅ Saved text MoM: {txt_path.resolve()}")

    print("\n✨ Minutes of Meeting generation complete!")
    print("\n📄 Generated files:")
    print(f"   - minutes_of_meeting.md")
    if action_items:
        print(f"   - action_items.json ({len(action_items)} items)")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate Minutes of Meeting from reviewed transcripts")
    ap.add_argument("--input", default="outputs/reviewed_transcripts.json", 
                    help="Path to reviewed_transcripts.json (default: outputs/reviewed_transcripts.json)")
    ap.add_argument("--out", default="outputs", help="Output directory")
    ap.add_argument("--model", default="openai/gpt-4o-mini", help="LLM model to use")
    ap.add_argument("--temperature", type=float, default=0.2, 
                    help="Temperature for generation (lower = less hallucination)")
    ap.add_argument("--format", default="markdown", choices=["markdown", "json", "both"],
                    help="Output format (markdown, json, or both)")
    args = ap.parse_args()
    
    main(args.input, args.out, args.model, args.temperature, args.format)
    
    # Example usage:
    # python crewAgent2.py                    # Uses default: outputs/reviewed_transcripts.json
    # python crewAgent2.py --input outputs/reviewed_transcripts.json --out outputs --format markdown