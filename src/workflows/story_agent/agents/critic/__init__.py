"""Critic Agent package — LLM-as-a-Judge evaluation pipeline.

Public API:
    CriticAgent  — main orchestrator (educational + coherence + G-EVAL + RAGAS/FABLES)
"""
from .agent import CriticAgent

__all__ = ["CriticAgent"]
