"""
Blackboard Architecture Wrapper
Wraps agentic_architectures.Blackboard for API integration.
"""
from .graph import create_blackboard_workflow
from .state import BlackboardWrapperState

__all__ = ["create_blackboard_workflow", "BlackboardWrapperState"]
