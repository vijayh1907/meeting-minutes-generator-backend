# src/agents/slack_notifier_agent.py
from crewai import Agent, LLM
from typing import Optional

def build_slack_notifier_agent(model: str = "openai/gpt-4o-mini",
                                temperature: float = 0.3,
                                tools: Optional[list] = None) -> Agent:
    """
    Build an agent specialized in sending Slack notifications about meetings and action items.
    
    Args:
        model: LLM model to use
        temperature: Temperature for generation (slightly higher for natural language)
        tools: List of tools available to the agent
        
    Returns:
        Configured CrewAI Agent
    """
    llm = LLM(model=model, temperature=temperature)
    
    return Agent(
        role="Slack Notification Specialist",
        goal=(
            "Send clear, informative, and well-formatted Slack notifications about meeting updates, "
            "action items, and task assignments. Ensure team members are promptly informed of their "
            "responsibilities and deadlines through engaging Slack messages."
        ),
        backstory=(
            "You are a communications expert who specializes in keeping teams informed and engaged. "
            "You understand that effective notifications are concise, actionable, and easy to scan. "
            "You know how to use Slack's formatting features (emojis, bold text, bullet points) to "
            "make messages both professional and engaging. You're skilled at highlighting the most "
            "important information - like urgent action items, approaching deadlines, and key decisions. "
            "You always include relevant context without overwhelming the reader, and you make it easy "
            "for team members to understand what's expected of them. Your notifications strike the "
            "perfect balance between being informative and being brief."
        ),
        llm=llm,
        tools=tools or [],
        allow_delegation=False,
        verbose=True,
    )