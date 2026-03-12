# app/core/use_cases/__init__.py
"""
Core use cases (application layer).

This package contains the orchestration layer of the text-generation runtime.
Use cases coordinate validated domain inputs with ports and bridges, while
keeping planning, lexical resolution, and realization concerns separated.

Primary pipeline
----------------
The canonical generation flow is:

    Frame -> plan -> lexical resolution -> realize -> surface result

Responsibilities
----------------
Use cases in this package may:
1. Validate and normalize request/domain inputs.
2. Invoke planner, lexical resolver, and realizer ports.
3. Coordinate compatibility bridges between legacy frame-based code and the
   construction-centered runtime.
4. Return canonical domain results without embedding infrastructure logic.

Notes
-----
- `GenerateText` is the high-level orchestration entry point.
- `PlanText` isolates sentence/construction planning.
- `RealizeText` isolates rendering of a canonical construction plan.
- Language build/onboarding workflows remain separate operational use cases.
"""

from .generate_text import GenerateText
from .plan_text import PlanText
from .realize_text import RealizeText
from .build_language import BuildLanguage
from .onboard_language_saga import OnboardLanguageSaga

__all__ = [
    "GenerateText",
    "PlanText",
    "RealizeText",
    "BuildLanguage",
    "OnboardLanguageSaga",
]