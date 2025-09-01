# src/tasks/classify_task.py
from crewai import Task

def build_batch_classification_task(transcript_path: str, agent) -> Task:
    """
    Single task that asks the agent to call TranscriptReader and return
    a JSON array of objects: {raw_transcript_line, category, tags, confidence, notes}.
    """
    description = (
        f"Use TranscriptReader on '{transcript_path}' to read the transcript into a list of items "
        "(each with id and text). For every item, emit one JSON object with keys:\n"
        "  - raw_transcript_line: the original text\n"
        "  - category: one of ['Action','Question','Discussion']\n"
        "  - tags: a short list of keywords\n"
        "  - confidence: number 0..1\n"
        "  - notes: short reason for the label\n\n"
        "Return a SINGLE JSON ARRAY containing all objects. "
        "Do not include any extra commentary. Strict JSON only."
    )
    return Task(
        description=description,
        expected_output="A JSON array of objects with keys: raw_transcript_line, category, tags, confidence, notes.",
        agent=agent,
        # output_json=True,   # CrewAI will parse to a Python list
        name="BatchTranscriptClassification",
    )
