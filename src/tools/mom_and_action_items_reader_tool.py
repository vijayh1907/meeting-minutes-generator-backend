# src/tools/mom_and_action_items_reader_tool.py
from crewai.tools import BaseTool
from pathlib import Path
import json
from typing import Dict, Any

class MomAndActionItemsReaderTool(BaseTool):
    name: str = "MomAndActionItemsReader"
    description: str = (
        "Reads both the Minutes of Meeting markdown file and the reviewed action items JSON file. "
        "Returns a structured dictionary containing the original MoM content and the reviewed action items "
        "that need to be merged into the action items section."
    )

    def _run(self, mom_path: str, action_items_path: str) -> Dict[str, Any]:
        """
        Read both files and return structured data for merging.
        
        Args:
            mom_path: Path to the minutes_of_meeting.md file
            action_items_path: Path to the reviewed_action_items.json file
            
        Returns:
            Dictionary with 'original_mom' and 'reviewed_action_items'
        """
        try:
            # Read the MoM markdown file
            mom_file = Path(mom_path)
            if not mom_file.exists():
                return {
                    "error": f"MoM file not found: {mom_path}",
                    "original_mom": None,
                    "reviewed_action_items": None
                }
            
            with open(mom_file, 'r', encoding='utf-8') as f:
                mom_content = f.read()
            
            # Read the reviewed action items JSON
            action_items_file = Path(action_items_path)
            if not action_items_file.exists():
                return {
                    "error": f"Action items file not found: {action_items_path}",
                    "original_mom": mom_content,
                    "reviewed_action_items": None
                }
            
            with open(action_items_file, 'r', encoding='utf-8') as f:
                action_items_data = json.load(f)
            
            return {
                "success": True,
                "original_mom": mom_content,
                "reviewed_action_items": action_items_data.get('action_items', []),
                "meeting_date": action_items_data.get('meeting_date'),
                "total_items": action_items_data.get('total_items', 0),
                "reviewed_at": action_items_data.get('reviewed_at')
            }
            
        except Exception as e:
            return {
                "error": f"Error reading files: {str(e)}",
                "original_mom": None,
                "reviewed_action_items": None
            }