# src/tools/transcript_reader_tool.py
from crewai.tools import BaseTool
from pathlib import Path
import re, sys

class TranscriptReaderTool(BaseTool):
    name: str = "TranscriptReader"
    description: str = (
        "Reads a transcript (.txt, .docx, .pdf) and returns a list of {id, text} "
        "by splitting into non-empty lines. If a timestamp is present, it's removed. "
        "IDs are serial (seg_0001, seg_0002, ...)."
    )

    _TS = re.compile(r"^\s*\[?\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*\]?\s*[:\-–]?\s*")

    def _read_text(self, p: Path) -> str:
        suf = p.suffix.lower()
        if suf == ".txt":
            return p.read_text(encoding="utf-8", errors="ignore")
        elif suf == ".docx":
            try:
                from docx import Document
            except ModuleNotFoundError as e:
                raise RuntimeError(
                    f"'python-docx' is not installed in this kernel ({sys.executable}). "
                    f"Install with: {sys.executable} -m pip install -U python-docx"
                ) from e
            doc = Document(str(p))
            return "\n".join(par.text for par in doc.paragraphs)
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
        s = re.sub(r"^\s*(?:[-•]\s+|\d+[\)\.]\s+)", "", s)   # bullets like “- ”, “1) ”
        s = self._TS.sub("", s)                              # strip optional timestamp
        return s.strip()

    def _run(self, path: str):
        p = Path(path)
        text = self._read_text(p)
        items = []
        for raw in text.splitlines():
            cleaned = self._clean_line(raw)
            if not cleaned:
                continue
            items.append({"id": f"seg_{len(items)+1:04d}", "text": cleaned})
        return items
