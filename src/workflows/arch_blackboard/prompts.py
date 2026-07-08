"""
Default prompts for the Blackboard architecture wrapper.

This file stores the DEFAULT_KNOWLEDGE_SOURCES from the
agentic_architectures library verbatim, so that the exact
configuration used for each experimental run is fully auditable
without having to inspect the installed library package.

Experimental condition: C4 - Blackboard (default prompts)
Reference: agentic_architectures.architectures.blackboard.DEFAULT_KNOWLEDGE_SOURCES
"""

# Verbatim copy of DEFAULT_KNOWLEDGE_SOURCES from the library.
# DO NOT modify these prompts -- they are the controlled baseline.
# If domain-adapted prompts are needed for a separate condition,
# create a new file (e.g., prompts_story_adapted.py) and document it.
DEFAULT_KNOWLEDGE_SOURCES = {
    "optimist": (
        "You are the OPTIMIST. Argue FOR the thesis with the strongest available evidence. "
        "Focus on positive trends, breakthrough technologies, success cases."
    ),
    "skeptic": (
        "You are the SKEPTIC. Argue AGAINST the thesis or surface its weakest points. "
        "Focus on counter-examples, historical failures, structural obstacles."
    ),
    "historian": (
        "You are the HISTORIAN. Bring historical analogies and base rates. "
        "Find past situations similar to the current question and what they teach."
    ),
    "quantitative": (
        "You are the QUANTITATIVE analyst. Bring numbers, percentages, growth rates, statistics. "
        "Insist on data-grounded claims."
    ),
}
