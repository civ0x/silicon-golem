# Silicon Golem — Python package
# SDK, orchestrator, validator, learner model, skill library

# Re-export the SDK so `from golem import *` works
from .sdk import *  # noqa: F401,F403
from .sdk import __all__, connect, disconnect  # noqa: F401
