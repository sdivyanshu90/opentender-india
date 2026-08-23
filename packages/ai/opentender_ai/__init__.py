"""OpenTender AI layer: budgeted, cached, citation-first LLM tasks.

Design rules (spec #8-#13, #35-#40):
- OPENROUTER_API_KEY only ever read from the environment.
- Free models are discovered at runtime; none are hard-coded as required.
- Every task has a versioned prompt + JSON schema; malformed output is repaired
  deterministically or rejected - never published.
- Tender/document text is untrusted DATA; prompts enforce strict boundaries.
"""

__version__ = "0.1.0"
