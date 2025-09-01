# crew.py
import os
import json
import re
from dotenv import load_dotenv
from pathlib import Path
from crewai import Crew, Process
from ast import literal_eval

from src.tools.transcript_reader_tool import TranscriptReaderTool
from src.agents.meeting_classifier_agent import build_classifier_agent
from src.tasks.classify_task import build_batch_classification_task
from src.io_utils import save_json, save_csv

def clean_code_fence(s: str) -> str:
    # strip surrounding ``` or ```json fences if present
    return re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", s, flags=re.IGNORECASE)

def coerce_to_list(obj):
    """Return a list of dicts from raw TaskOutput, regardless of format."""
    from ast import literal_eval
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return [obj]
    if isinstance(obj, str):
        s = clean_code_fence(obj.strip())
        # try JSON first
        try:
            v = json.loads(s)
            return v if isinstance(v, list) else [v]
        except Exception:
            pass
        # then Python-literal style
        try:
            v = literal_eval(s)
            return v if isinstance(v, list) else [v]
        except Exception:
            # last resort: try line-delimited JSON
            recs = []
            for line in s.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except Exception:
                    recs.append({"parse_error": line})
            return recs
    # unknown shape
    return [{"parse_error": repr(obj)}]



def main(in_path: str, out_dir: str | Path = "outputs",
         model: str = "openai/gpt-4o-mini", temperature: float = 0.1):
    load_dotenv()

    # 1) Tools
    reader_tool = TranscriptReaderTool()

    # 2) Agent
    agent = build_classifier_agent(model=model, temperature=temperature, tools=[reader_tool])

    # 3) Task (batch—agent will call TranscriptReader itself)
    task = build_batch_classification_task(in_path, agent)

    # 4) Crew & kickoff
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()  # CrewOutput

    # 5) Collect parsed JSON list (because output_json=True)
    #    If the model complied, result.tasks_output[0].pydantic/json_dict will be set,
    #    but .raw is fine too. CrewAI returns Python list directly in .raw sometimes.
    records = None
    
    # Prefer the structured output from the first (and only) task
    if result.tasks_output:
        records = []
        for t in result.tasks_output:
            records.extend(coerce_to_list(t.raw))
    else:
        records = coerce_to_list(result.raw)

    # if result.tasks_output and getattr(result.tasks_output[0], "raw", None):
    #     all_raws = [t.raw for t in result.tasks_output]
    #     records = list()
    #     for raw in all_raws:
    #         cleaned = raw.strip("`")
    #         records.extend(literal_eval(cleaned))
    # else:
    #     # fallback: try top-level .raw
    #     records = result.raw
    #     if isinstance(records, str):
    #         records = json.loads(records)

    # 6) Save
    out_dir = Path(out_dir)
    json_path = save_json(records, out_dir / "classified_transcripts.json")
    csv_path  = save_csv(records,  out_dir / "classified_transcripts.csv")

    print(f"✅ Saved {len(records)} rows")
    print(f"   JSON: {json_path.resolve()}")
    print(f"   CSV : {csv_path.resolve()}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to transcript .txt/.pdf/.docx")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--model", default="openai/gpt-4o-mini")
    ap.add_argument("--temperature", type=float, default=0.1)
    args = ap.parse_args()
    main(args.input, args.out, args.model, args.temperature)
    # python crew.py --input call_transcript.txt --out outputs