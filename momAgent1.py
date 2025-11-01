import os
from dotenv import load_dotenv
load_dotenv()

# Get the key
api_key = os.getenv("OPENAI_API_KEY")
print(api_key)  # Just to check (don’t print in production!)

from crewai import LLM
open_ai_llm = LLM(
        model="openai/gpt-4o-mini",
        temperature=0.1
        )

from crewai.tools import BaseTool
from pathlib import Path
# from docx import Document
import re, sys

class TranscriptReaderTool(BaseTool):
    name: str = "TranscriptReader"
    description: str = (
        "Reads a transcript (.txt, .docx, .pdf) and returns a list of {id, text} "
        "by splitting into non-empty lines. If a timestamp is present, it's removed. "
        "IDs are serial (seg_0001, seg_0002, ...)."
    )

    # regex to OPTIONALY strip leading timestamps like [00:12], [01:02:33], 00:12, 1:02:33
    _TS = re.compile(r"^\s*\[?\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*\]?\s*[:\-–]?\s*")

    def _read_text(self, p: Path) -> str:
        suf = p.suffix.lower()
        if suf == ".txt":
            return p.read_text(encoding="utf-8", errors="ignore")
        # elif suf == ".docx":
        #     try:
        #         from docx import Document   # requires python-docx
        #     except ModuleNotFoundError as e:
        #         raise RuntimeError(
        #             f"'python-docx' is not installed in this kernel ({sys.executable}). "
        #             f"Install with: {sys.executable} -m pip install -U python-docx"
        #         ) from e
        #     doc = Document(str(p))
        #     return "\n".join(par.text for par in doc.paragraphs)
        elif suf == ".pdf":
            try:
                from pypdf import PdfReader
            except ModuleNotFoundError as e:
                raise RuntimeError(
                    f"'pypdf' is not installed in this kernel ({sys.executable}). "
                    f"Install with: {sys.executable} -m pip install -U pypdf"
                ) from e
            reader = PdfReader(str(p))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        else:
            raise ValueError(f"Unsupported file type: {p.suffix}")

    def _clean_line(self, line: str) -> str:
        s = line.strip()
        if not s:
            return ""
        # remove bullets/numbers like "- ", "• ", "1) ", "1. "
        s = re.sub(r"^\s*(?:[-•]\s+|\d+[\)\.]\s+)", "", s)
        # strip optional timestamp if present
        s = self._TS.sub("", s)
        return s.strip()

    def _run(self, path: str):
        p = Path(path)
        text = self._read_text(p)

        items = []
        for raw in text.splitlines():
            cleaned = self._clean_line(raw)
            if not cleaned:
                continue
            items.append({
                "id": f"seg_{len(items)+1:04d}",   # SERIAL ID
                "text": cleaned
            })
        # optional: keep it quiet in agents; return the data
        return items


# # --- One input line (you can loop over many) ---
# line = "[0:22] So Sean will be taking it over."
# # --- Task ---
# prompt = f"""
# Return ONLY JSON with keys: category, tags, confidence, notes.
# Text:
# {line}
# """

def get_prompt(line):
    prompt = f"""
        Return ONLY JSON with keys: raw_transcript_line, category, tags, confidence, notes.
        Text:
        {line}
        """
    return prompt


from crewai import Agent, Task, Crew, Process
import os, json


# --- Agent ---
classifier_agent = Agent(
    role="Meeting Snippet Classifier",
    goal=("Given a short line from a meeting transcript, output JSON with: "
          "raw_transcript_line, category (Action|Question|Discussion), tags[], confidence[0..1], notes."
          "do not introduce any new catagory apart from what is mentioned above."),
    backstory=("You classify meeting lines conservatively. Only give high confidence "
               "when it’s obvious."),
    llm=open_ai_llm,
    tools=[TranscriptReaderTool()],
    allow_delegation=False,
    verbose=False,
)

transcript_path = "call_transcript.txt"
prompt = f"Use TranscriptReader to read {transcript_path} and return the parsed lines. For each line classify into JSON with keys: category, tags, confidence, notes."
# --- Build Tasks for each transcript line ---
classifier_task = Task(
        description= prompt,
        expected_output="Strict JSON: {{'category': 'Action|Question|Discussion', 'tags': [...], 'confidence': 0-1, 'notes': '...'}}",
        agent=classifier_agent,
        # output_json=True,   # CrewAI will parse to dict
    )



crew = Crew(
    agents=[classifier_agent],
    tasks=[classifier_task],
    process=Process.sequential
)

result = crew.kickoff()

import json
from pathlib import Path
from ast import literal_eval


all_raws = [t.raw for t in result.tasks_output]
records = list()
for raw in all_raws:
    cleaned = raw.strip("`")
    records.extend(literal_eval(cleaned))


# save as JSON array
out_path = Path("classified_transcripts.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ Saved {len(records)} records to {out_path.resolve()}")
