"""
Debate Architecture Wrapper
Wraps agentic_architectures.Debate for API integration.
"""
from .graph import create_debate_workflow
from .state import DebateWrapperState

__all__ = ["create_debate_workflow", "DebateWrapperState"]
