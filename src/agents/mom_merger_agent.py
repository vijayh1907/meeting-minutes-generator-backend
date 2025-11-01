# src/agents/mom_merger_agent.py
from crewai import Agent, LLM
from typing import Optional

def build_mom_merger_agent(model: str = "openai/gpt-4o-mini",
                           temperature: float = 0.2,
                           tools: Optional[list] = None) -> Agent:
    """
    Build an agent specialized in merging reviewed action items with MoM.
    
    Args:
        model: LLM model to use
        temperature: Temperature for generation (lower = more precise)
        tools: List of tools available to the agent
        
    Returns:
        Configured CrewAI Agent
    """
    llm = LLM(model=model, temperature=temperature)
    
    return Agent(
        role="Minutes of Meeting Merger Specialist",
        goal=(
            "Intelligently merge reviewed action items with existing Minutes of Meeting (MoM) documents. "
            "Update ONLY the Action Items section with the reviewed data while preserving all other sections "
            "and maintaining professional formatting. Calculate missing due dates based on the meeting date "
            "when day names are mentioned."
        ),
        backstory=(
            "You are a meticulous documentation specialist with expertise in maintaining professional meeting records. "
            "You understand that reviewed action items contain important updates like assigned owners, calculated due dates, "
            "priorities, and status information that must be accurately reflected in the official MoM. "
            "You are EXTREMELY careful to preserve the original structure and content of all other sections while "
            "updating only the action items section. You have excellent date calculation skills - when an action item "
            "mentions a day name (like 'Monday' or 'Wednesday') without a calculated date, you determine the actual "
            "calendar date by finding the next occurrence of that day after the meeting date. "
            "You know that each action item should clearly display: description, owner (with email), due date "
            "(with calculated calendar date), priority, and status. "
            "You format action items in a clean, scannable way that stakeholders can quickly understand."
        ),
        llm=llm,
        tools=tools or [],
        allow_delegation=False,
        verbose=False,
    )