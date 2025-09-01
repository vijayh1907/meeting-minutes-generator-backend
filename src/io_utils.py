# src/io_utils.py
import json
from pathlib import Path
from typing import Any, List, Dict
import pandas as pd

def save_json(data: Any, path: str | Path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p

def save_csv(records: List[Dict], path: str | Path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    # prettify tags column if present
    if "tags" in df.columns:
        df["tags"] = df["tags"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
    df.to_csv(p, index=False)
    return p
