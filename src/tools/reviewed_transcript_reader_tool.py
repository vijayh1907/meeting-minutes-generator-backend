# src/tools/reviewed_transcript_reader_tool.py
from crewai.tools import BaseTool
from pathlib import Path
import json
from typing import Dict, List, Any

class ReviewedTranscriptReaderTool(BaseTool):
    name: str = "ReviewedTranscriptReader"
    description: str = (
        "Reads a reviewed_transcripts.json file and returns structured data "
        "containing meeting metadata and categorized transcript items. "
        "Each item includes: raw_transcript_line, category (Action/Question/Discussion/Greetings), "
        "tags, confidence, and notes."
    )

    def _extract_meeting_metadata(self, transcripts: List[Dict]) -> Dict[str, Any]:
        """
        Extract meeting metadata from the transcript items.
        Looks for items tagged with 'date', 'time', 'team', 'participants', etc.
        """
        metadata = {
            "title": None,
            "date": None,
            "time": None,
            "team": None,
            "participants": None,
            "duration": None
        }
        
        for item in transcripts[:10]:  # Check first 10 items for metadata
            raw_line = item.get("raw_transcript_line", "")
            tags = item.get("tags", [])
            
            # Extract title
            if "meeting" in tags and "transcript" in tags and raw_line.startswith("#"):
                metadata["title"] = raw_line.lstrip("#").strip()
            
            # Extract date
            if "date" in tags and "**Date:**" in raw_line:
                metadata["date"] = raw_line.replace("**Date:**", "").strip()
            
            # Extract time
            if "time" in tags and "**Time:**" in raw_line:
                metadata["time"] = raw_line.replace("**Time:**", "").strip()
            
            # Extract team
            if "team" in tags and "**Team:**" in raw_line:
                metadata["team"] = raw_line.replace("**Team:**", "").strip()
            
            # Extract participants
            if "participants" in tags and "**Participants:**" in raw_line:
                metadata["participants"] = raw_line.replace("**Participants:**", "").strip()
        
        return metadata

    def _categorize_items(self, transcripts: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group transcript items by category.
        """
        categorized = {
            "Actions": [],
            "Questions": [],
            "Discussions": [],
            "Greetings": [],
            "Technical_Issues": [],
            "Other": []
        }
        
        for item in transcripts:
            category = item.get("category", "Other")
            tags = item.get("tags", [])
            
            # Skip metadata and separator lines
            if item.get("confidence", 1.0) < 0.2:
                continue
            
            # Categorize technical issues separately
            if any(tag in tags for tag in ["audio", "WiFi", "screen", "echo", "background noise"]):
                continue  # Skip technical issues for MoM
            
            # Skip greeting/closing items
            if category == "Greetings" or "goodbye" in tags or "greeting" in tags:
                continue
            
            if category == "Action":
                categorized["Actions"].append(item)
            elif category == "Question":
                categorized["Questions"].append(item)
            elif category == "Discussion":
                categorized["Discussions"].append(item)
            else:
                categorized["Other"].append(item)
        
        return categorized

    def _extract_key_topics(self, transcripts: List[Dict]) -> List[str]:
        """
        Extract key topics/themes from the transcript based on tags and content.
        """
        topic_counts = {}
        
        for item in transcripts:
            tags = item.get("tags", [])
            category = item.get("category", "")
            
            # Skip non-substantial items
            if item.get("confidence", 0) < 0.6:
                continue
            
            # Skip technical and greeting tags
            skip_tags = ["audio", "WiFi", "screen", "echo", "background noise", 
                        "greeting", "goodbye", "mute", "recording"]
            
            for tag in tags:
                if tag not in skip_tags and len(tag) > 2:
                    topic_counts[tag] = topic_counts.get(tag, 0) + 1
        
        # Return top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics[:10]]

    def _extract_action_items(self, action_items: List[Dict]) -> List[Dict]:
        """
        Extract and format action items with relevant details.
        """
        formatted_actions = []
        print(action_items[:20])  # Debug: print first 20 action items
        for item in action_items:
            raw_line = item.get("raw_transcript_line", "")
            tags = item.get("tags", [])
            notes = item.get("notes", "")
            
            # Skip technical actions
            skip_tags = ["audio", "WiFi", "mute", "background noise", "phone", "silence"]
            if any(tag in tags for tag in skip_tags):
                continue
            
            formatted_actions.append({
                "description": raw_line,
                "tags": tags,
                "context": notes
            })
        
        return formatted_actions

    def _run(self, path: str) -> Dict[str, Any]:
        """
        Read and parse the reviewed_transcripts.json file.
        
        Args:
            path: Path to reviewed_transcripts.json
            
        Returns:
            Dictionary containing structured meeting data
        """
        p = Path(path)
        
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if p.suffix.lower() != ".json":
            raise ValueError(f"Expected .json file, got: {p.suffix}")
        
        # Load the JSON file
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract transcripts
        transcripts = data.get("transcripts", [])
        meeting_id = data.get("meeting_id")
        
        # Process the data
        metadata = self._extract_meeting_metadata(transcripts)
        categorized = self._categorize_items(transcripts)
        key_topics = self._extract_key_topics(transcripts)
        action_items = self._extract_action_items(categorized["Actions"])
        
        # Return structured data
        return {
            "meeting_id": meeting_id,
            "metadata": metadata,
            "key_topics": key_topics,
            "action_items": action_items,
            "categorized_items": categorized,
            "total_items": len(transcripts),
            "summary_stats": {
                "actions": len(categorized["Actions"]),
                "questions": len(categorized["Questions"]),
                "discussions": len(categorized["Discussions"])
            }
        }