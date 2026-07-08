"""
Bilingual prompt loader for story agent workflow.
Loads prompts from language-specific directories (prompts/id/, prompts/en/).
"""

from typing import Optional, List, Any
from pathlib import Path
from loguru import logger

# Cache for registries by language
_registries: dict[str, 'PromptRegistry'] = {}


class PromptRegistry:
    """Registry that loads prompts from language-specific directories."""
    
    PROMPT_NAMES = [
        "supervisor", "researcher_planner", "researcher_web",
        "planner_unified", "planner_parser", "planner_short_guide",
        "writer", "writer_instructions", "writer_user", "writer_revision", "writer_revision_fallback",
        "writer_diagram", "writer_diagram_system", "writer_diagram_fix",
        "director",
        "critic", "critic_coherence",
        "image_gen_style", "image_gen_scenes",
        "summarizer_unified", "summarizer_summary", "summarizer_sentiment",
        "summarizer_actions", "summarizer_interactions", "summarizer_relationships",
        "state_tracker"
    ]
    
    def __init__(self, language: str = "id"):
        self._language = language
        self._prompts: dict[str, str] = {}
        self._load_all()
    
    def _load_all(self):
        prompts_dir = Path(__file__).parent / "prompts" / self._language
        if not prompts_dir.exists():
            # Create if it doesn't exist to prevent immediate crash during migration
            prompts_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(f"[PROMPT_REGISTRY] Directory not found, created: {prompts_dir}")
            
        for name in self.PROMPT_NAMES:
            path = prompts_dir / f"{name}.md"
            if not path.exists():
                # For now, if the file doesn't exist in the specific language dir,
                # fall back to the root prompts/ dir (for backward compatibility during migration)
                root_path = Path(__file__).parent / "prompts" / f"{name}.md"
                if root_path.exists():
                    self._prompts[name] = root_path.read_text(encoding="utf-8").strip()
                else:
                    logger.warning(f"[PROMPT_REGISTRY] Prompt file not found: {name}")
                    self._prompts[name] = "" # Empty fallback mapping
            else:
                self._prompts[name] = path.read_text(encoding="utf-8").strip()
        
        logger.info(f"[PROMPTS] Loaded {len(self._prompts)} prompts ({self._language})")
    
    def get(self, name: str) -> str:
        if name not in self._prompts:
            raise KeyError(f"Unknown prompt: {name}")
        return self._prompts[name]
    
    @property
    def language(self) -> str:
        return self._language


def get_registry(language: Optional[str] = None) -> PromptRegistry:
    """
    Get a prompt registry for the specified language.
    If no language is specified, uses LanguageConfig.SYSTEM_LANGUAGE.
    """
    global _registries
    
    if language is None:
        try:
            from settings import LanguageConfig
            language = LanguageConfig.SYSTEM_LANGUAGE
        except ImportError:
            language = "id" # Fallback
            
    if language not in _registries:
        _registries[language] = PromptRegistry(language)
        
    return _registries[language]


def init_registry(language: str):
    """
    Initialize/refresh the prompt registry for a specific language.
    """
    global _registries
    _registries[language] = PromptRegistry(language)
    return _registries[language]


# Backward compatibility - lazy properties
# Agents can still do: from ..prompts import WRITER_PROMPT
# But now it goes through the registry
def __getattr__(name: str):
    """Module-level __getattr__ for backward-compatible access."""
    mapping = {
        "SUPERVISOR_PROMPT": "supervisor",
        "RESEARCH_PLANNER_PROMPT": "researcher_planner",
        "PLANNER_UNIFIED_PROMPT": "planner_unified",
        "SUMMARIZER_UNIFIED_PROMPT": "summarizer_unified",
        "DIAGRAM_SYSTEM_PROMPT": "writer_diagram_system",
        "DIAGRAM_USER_PROMPT": "writer_diagram",
        "IMAGE_GEN_STYLE_PROMPT": "image_gen_style",
        "IMAGE_GEN_SCENES_PROMPT": "image_gen_scenes",
        "CRITIC_COHERENCE_PROMPT": "critic_coherence",
        "RESEARCHER_WEB_PROMPT": "researcher_web",
        "WRITER_INSTRUCTIONS_PROMPT": "writer_instructions",
        "WRITER_USER_PROMPT": "writer_user",
        "SUMMARIZER_SUMMARY_PROMPT": "summarizer_summary",
        "SUMMARIZER_SENTIMENT_PROMPT": "summarizer_sentiment",
        "SUMMARIZER_ACTIONS_PROMPT": "summarizer_actions",
        "SUMMARIZER_INTERACTIONS_PROMPT": "summarizer_interactions",
        "SUMMARIZER_RELATIONSHIPS_PROMPT": "summarizer_relationships",
    }
    if name in mapping:
        return get_registry().get(mapping[name])
    raise AttributeError(f"module 'prompts' has no attribute '{name}'")

