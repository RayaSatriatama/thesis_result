"""
Default configuration constants for the STORM architecture wrapper.

Stores the hyperparameter defaults used in the notebook run so that
the exact configuration for each experimental run is fully auditable.

Experimental condition: STORM (Shao et al., 2024. arXiv:2402.14207)
Reference: agentic_architectures.architectures.STORM
"""

# Verbatim defaults from the notebook (multi_agent_storm.ipynb).
# DO NOT modify these constants -- they are the controlled baseline.
# Paper defaults: n_perspectives=5, questions_per_perspective=5.
# Notebook uses reduced values for cost.
DEFAULT_N_PERSPECTIVES = 3
DEFAULT_QUESTIONS_PER_PERSPECTIVE = 2
