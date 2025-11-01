# src/agents/mom_generator_agent.py
from crewai import Agent, LLM
from typing import Optional

def build_mom_generator_agent(model: str = "openai/gpt-4o-mini",
                               temperature: float = 0.3,
                               tools: Optional[list] = None) -> Agent:
    """
    Build an agent specialized in generating professional Minutes of Meeting (MoM).
    
    Args:
        model: LLM model to use
        temperature: Temperature for generation (higher = more creative)
        tools: List of tools available to the agent
        
    Returns:
        Configured CrewAI Agent
    """
    llm = LLM(model=model, temperature=temperature)
    
    return Agent(
        role="Minutes of Meeting Generator",
        goal=(
            "Generate clear, professional, and comprehensive Minutes of Meeting (MoM) "
            "from reviewed meeting transcripts. The MoM should capture key decisions, "
            "action items, discussions, and follow-up tasks in a structured format."
        ),
        backstory=(
            "You are an experienced meeting coordinator and documentation specialist "
            "with years of experience creating professional meeting minutes. "
            "You are EXTREMELY careful to only document what actually happened in meetings - "
            "you NEVER invent, assume, or hallucinate information that wasn't discussed. "
            "Your reputation depends on accuracy and faithfulness to the source material. "
            "You understand the importance of clear action items with owners and deadlines, "
            "and you know how to present information in a way that's useful for stakeholders "
            "who weren't present at the meeting - but ONLY using information from the actual transcript."
        ),
        llm=llm,
        tools=tools or [],
        allow_delegation=False,
        verbose=False,
    )