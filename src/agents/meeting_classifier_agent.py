# src/agents/meeting_classifier_agent.py
from crewai import Agent, LLM
from typing import Optional

def build_classifier_agent(model: str = "openai/gpt-4o-mini",
                           temperature: float = 0.1,
                           tools: Optional[list] = None) -> Agent:
    llm = LLM(model=model, temperature=temperature)
    return Agent(
        role="Meeting Snippet Classifier",
        goal=("Given transcript lines, return JSON with fields: "
              "raw_transcript_line, category (Action|Question|Discussion), "
              "tags[], confidence (0..1), notes. "
              "Do not invent new categories."),
        backstory=("You classify meeting lines conservatively. "
                   "Only give high confidence when it’s obvious."),
        llm=llm,
        tools=tools or [],
        allow_delegation=False,
        verbose=False,
    )
