"""
Scenario-specific prompts.
Промпты для конкретных сценариев и тем.
"""

from ai.prompts.scenarios.marriage import (
    INFIDELITY_PROMPT,
    INTIMACY_ISSUES_PROMPT,
    CONFLICT_PROMPT,
)
from ai.prompts.scenarios.motherhood import (
    BURNOUT_MOM_PROMPT,
    WORKING_MOM_GUILT_PROMPT,
)
from ai.prompts.scenarios.crisis import (
    CRISIS_RESPONSE_PROMPT,
)

__all__ = [
    "INFIDELITY_PROMPT",
    "INTIMACY_ISSUES_PROMPT",
    "CONFLICT_PROMPT",
    "BURNOUT_MOM_PROMPT",
    "WORKING_MOM_GUILT_PROMPT",
    "CRISIS_RESPONSE_PROMPT",
]
