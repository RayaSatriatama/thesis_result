"""
Default prompts for the Debate architecture wrapper.

Verbatim copy of Debate.AGENT_PERSONAS from the agentic_architectures library,
stored here so the exact configuration used per experimental run is fully
auditable without inspecting the installed package.

Experimental condition: Debate (Du et al., 2023. arXiv:2305.14325)
Reference: agentic_architectures.architectures.debate.Debate.AGENT_PERSONAS
"""

# Verbatim copy of Debate.AGENT_PERSONAS from the library.
# DO NOT modify these prompts -- they are the controlled baseline.
# If domain-adapted personas are needed for a separate condition,
# create a new file (e.g., prompts_custom.py) and document it separately.
AGENT_PERSONAS = [
    "You are Agent A: rigorous, demands step-by-step reasoning before committing to an answer.",
    "You are Agent B: skeptical, actively looks for counterexamples and edge cases.",
    "You are Agent C: pragmatic, focuses on which answer best fits all available evidence.",
]
