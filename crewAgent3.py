# crewAgent3.py
import os
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

def main(mom_path: str = "outputs/minutes_of_meeting.md",
         action_items_path: str = "outputs/reviewed_action_items.json",
         out_dir: str = "outputs",
         model: str = "openai/gpt-4o-mini",
         temperature: float = 0.2,
         backup: bool = True):
    """
    Merge reviewed action items with Minutes of Meeting using CrewAI.
    
    Args:
        mom_path: Path to the original MoM markdown file
        action_items_path: Path to reviewed_action_items.json
        out_dir: Output directory for the updated MoM
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
        return
    
    if not action_items_file.exists():
        print(f"ERROR: Action items file not found: {action_items_file.absolute()}")
        return
    
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
    
    # Save the merged MoM as updated_minutes_of_meeting.md
    output_file = out_dir / "updated_minutes_of_meeting.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(merged_content)
    
    print()
    print("=" * 70)
    print("Update Complete!")
    print("=" * 70)
    print(f"Updated MoM saved: {output_file.absolute()}")
    print(f"   File size: {output_file.stat().st_size / 1024:.2f} KB")
    print(f"Original MoM preserved: {mom_file.name}")
    if backup:
        print(f"Backup also created: {backup_path.name}")
    print()

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
  python crewAgent3.py --mom outputs/minutes_of_meeting.md --items outputs/reviewed_action_items.json
  
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
        default="outputs/reviewed_action_items.json",
        help="Path to reviewed_action_items.json (default: outputs/reviewed_action_items.json)"
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

# python crewAgent3.py --mom outputs/minutes_of_meeting.md --items outputs/reviewed_action_items.json --no-backup