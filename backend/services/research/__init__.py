"""Nivesh Research Engine: backend side (spec 7).

Every number in a stock report is computed by the ml-engine and travels as a
typed Fact. This package turns those facts into prose without letting a
language model choose or type a number:

- ``facts``: the LLM payload (ok facts, band phrases, allowed names, hash);
- ``validator``: the deterministic grounding validator ``gv-1``;
- ``templates``: fixed texts (tier, disclaimer, AI disclosure, legacy) and the
  ``tf-1`` template narrative;
- ``formatter``: the DeepSeek ``rf-1`` formatter with retry and fallback.

Modules are imported explicitly; nothing is re-exported here, so importing a
sibling module (for example ``config``) never loads the LLM client.
"""
