"""Grounding validator ``gv-1`` (spec 7.5). Pure functions, no I/O.

The LLM may only write placeholders such as ``{{risk.vol_ewma_ann_pct}}``; the
server substitutes each with its display string. Any leftover digit or number
word, advice/forecast/causal wording, ungrounded qualifier or direction word,
foreign company or malformed output fails the check, and the caller falls back
to the fixed template. Text is scanned after masking placeholders, allowed
names and exact fact labels, so server-written labels such as
"Largest fall from a peak, last 3 years" never trip the scan.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process

VALIDATOR_VERSION = "gv-1"
LEXICON_VERSION = "lx-1"

SECTION_IDS: tuple[str, ...] = ("risk", "factor_profile", "fundamentals")
FIELDS: tuple[str, ...] = ("summary", *SECTION_IDS)
SECTION_PREFIX: dict[str, str] = {"risk": "risk.", "factor_profile": "factor.", "fundamentals": "fund."}
MAX_CHARS: dict[str, int] = {"summary": 450, "risk": 400, "factor_profile": 400, "fundamentals": 400}
MAX_SENTENCES = 3
MAX_WORDS = 25
DIRECTION_WINDOW = 6
FUZZY_CUTOFF = 92
ENTITY_WHITELIST = frozenset({"NSE", "BSE", "EWMA", "VAR", "CVAR", "ROE", "EBITDA", "EV", "TTM", "AI"})

PLACEHOLDER_RE = re.compile(r"\{\{([^{}]*)\}\}")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.?])\s+")
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S | re.I)
_P = "⟦P⟧"  # masked placeholder
_M = "⟦M⟧"  # masked allowed name or fact label
_TOKEN_RE = re.compile(r"⟦[PM]⟧|[^\W_]+(?:['’-][^\W_]+)*")
_CAP_WORD_RE = re.compile(r"[^\W\d_][\w&'’.-]*")
_UPPER_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9&-]{1,14}\b")

# 2. format
_URL_RE = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|in|net|org|io|co)\b", re.I)
_MARKDOWN_RE = re.compile(r"[*#`|]|\[[^\]]*\]\(|^\s*(?:- |•)", re.M)
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

# 5. literal_number (plus typed currency units: the display strings already carry ₹)
_NUMBER_WORDS = (
    "zero two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety "
    "hundred thousand lakh lac crore million billion trillion half double twice triple thrice "
    "dozen percent rs inr rupee"
).split()
_NUMBER_RE = re.compile(r"\d|\b(?:" + "|".join(_NUMBER_WORDS) + r"|per\s+cent)s?\b", re.I)


def _lexicon(*terms: str) -> re.Pattern[str]:
    """Word-bounded, case-insensitive alternation. 'x*' is a prefix; 're:' is a raw regex."""
    parts = []
    for term in terms:
        if term.startswith("re:"):
            parts.append(term[3:])
            continue
        prefix = term.endswith("*")
        pattern = re.escape(term.rstrip("*")).replace(r"\ ", r"\s+")
        parts.append(pattern + (r"\w*" if prefix else ""))
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.I)


# 6. lexicon lx-1. OPINION is a strict addition: rf-1 rule 6 bans these words
# outright, so a band placeholder must not license them as qualifiers.
LEXICON: dict[str, re.Pattern[str]] = {
    "ADVICE": _lexicon(
        "buy", "sell", "hold", "accumulate", "add to", "exit", "book profit", "switch to", "avoid", "trim",
        r"re:b[\W_]*u[\W_]*y", r"re:s[\W_]*e[\W_]*l[\W_]*l", r"re:h[\W_]*o[\W_]*l[\W_]*d",
    ),
    "RATING": _lexicon(
        "bullish", "bearish", "overweight", "underweight", "outperform", "underperform", "rating", "rated",
        "top pick", "best stock", "multibagger", "signal", "call",
    ),
    "TARGET": _lexicon(
        "target", "fair value", "intrinsic value", "upside", "downside", "stop loss", "stop-loss",
        "stoploss", "entry",
    ),
    "DIRECTIVE": _lexicon(
        "recommend*", "advis*", "suggest*", "should", "must", "ought", "you", "your", "we think", "we believe",
    ),
    "PROMISE": _lexicon("guarantee*", "assured", "risk-free", "sure-shot", "certain*", "definitely"),
    "FORECAST": _lexicon(
        "will", "shall", "going to", "may", "might", "could", "expect*", "likely", "unlikely", "poised",
        "set to", "forecast*", "predict*", "projected", "outlook", "probability", "chance", "odds",
    ),
    "EVIDENCE": _lexicon(
        "edge", "validated", "significant*", "reliable", "proven", "accurate", "accuracy", "predictive",
        "confidence", "confident", "track record", "model",
    ),
    "CAUSAL": _lexicon(
        "because", "due to", "driven by", "thanks to", "on the back of", "as a result of", "owing to", "led by",
    ),
    "REGISTRATION": _lexicon("SEBI", "registered", "regulator*"),
    "HINGLISH": _lexicon("kharid*", "khareed*", "bech*", "pakka*", "munafa*"),
    "OPINION": _lexicon("cheap", "expensive", "attractive", "undervalued", "overvalued", "risky", "safe"),
}

# 7. ungrounded_qualifier
_QUALIFIER_RE = _lexicon(
    "high", "low", "large", "small", "big", "cheap", "expensive", "strong", "weak", "attractive",
    "undervalued", "overvalued", "risky", "safe", "volatile", "stable", "healthy", "robust", "impressive",
    "worrying", "elevated", "modest", "substantial",
)

# 8. direction words
_UP_WORDS = frozenset({"rose", "gained", "up", "increased", "higher", "above", "outperformed"})
_DOWN_WORDS = frozenset({"fell", "declined", "down", "decreased", "lower", "below", "underperformed", "dropped"})


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    failures: list[dict[str, Any]] = field(default_factory=list)
    rendered: dict[str, Any] | None = None


def normalise_symbol(symbol: str) -> str:
    """'tcs.ns' -> 'TCS' (the form ``research_repo.known_symbols_and_names`` returns)."""
    s = str(symbol).strip().upper()
    for suffix in (".NS", ".BO"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


def render(obj: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    """Substitute every known placeholder with its display string, band phrase or date."""
    values: dict[str, str] = {f["id"]: f["display"] for f in payload.get("facts", [])}
    values.update(payload.get("bands", {}))
    values["as_of"] = payload["as_of"]

    def sub(text: str) -> str:
        return PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), text)

    sections = obj["sections"]
    return {"summary": sub(obj["summary"]), "sections": {k: sub(sections[k]) for k in SECTION_IDS}}


_Fail = Callable[..., None]


def _parse(raw: str | Mapping[str, Any], fail: _Fail) -> dict[str, Any] | None:
    """Rule 1 shape: exactly {summary, sections{risk, factor_profile, fundamentals}}, all strings."""
    if isinstance(raw, Mapping):
        obj: Any = raw
    else:
        text = str(raw).strip()
        fenced = _FENCE_RE.fullmatch(text)
        if fenced:
            text = fenced.group(1)
        try:
            obj = json.loads(text)
        except (TypeError, ValueError):
            fail("structure", token="not_json")
            return None
    if not isinstance(obj, Mapping) or set(obj) != {"summary", "sections"}:
        fail("structure", token="top_level_keys")
        return None
    sections = obj["sections"]
    if not isinstance(sections, Mapping) or set(sections) != set(SECTION_IDS):
        fail("structure", token="section_keys")
        return None
    texts = {"summary": obj["summary"], **{k: sections[k] for k in SECTION_IDS}}
    bad = [k for k, v in texts.items() if not isinstance(v, str)]
    for k in bad:
        fail("structure", k, token="not_a_string")
    if bad:
        return None
    return {"summary": obj["summary"], "sections": {k: sections[k] for k in SECTION_IDS}}


def _mask_pattern(payload: Mapping[str, Any]) -> re.Pattern[str] | None:
    terms = {str(n) for n in payload.get("allowed_names", []) if str(n).strip()}
    terms |= {str(f["label"]) for f in payload.get("facts", []) if str(f.get("label", "")).strip()}
    if not terms:
        return None
    ordered = sorted(terms, key=len, reverse=True)
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in ordered) + r")(?!\w)", re.I)


def _check_format(text: str, fname: str, fail: _Fail) -> None:
    if "!" in text:
        fail("format", fname, token="!")
    bare = PLACEHOLDER_RE.sub(" ", text)
    for rx in (_URL_RE, _MARKDOWN_RE):
        m = rx.search(bare)
        if m:
            fail("format", fname, token=m.group(0))
    for ch in text:
        if ch == "️" or unicodedata.category(ch) == "So":
            fail("format", fname, token=ch)
            break
    m = _DEVANAGARI_RE.search(text)
    if m:
        fail("lang", fname, token=m.group(0))


class _EntityIndex:
    """Known tickers and other companies' names, excluding the report's own company."""

    def __init__(self, payload: Mapping[str, Any], known_symbols: Iterable[str], company_names: Iterable[str]):
        own_symbol = normalise_symbol(payload.get("symbol", ""))
        self.symbols = {normalise_symbol(s) for s in known_symbols} - {own_symbol, ""}
        own_name = default_process(str(payload.get("company_name", "")))
        self.names: list[str] = []
        self.name_tokens: list[set[str]] = []
        for name in dict.fromkeys(str(n) for n in company_names):
            processed = default_process(name)
            if processed and processed != own_name:
                self.names.append(name)
                self.name_tokens.append(set(processed.split()))

    def fuzzy_match(self, ngram: str) -> str | None:
        tokens = set(default_process(ngram).split())
        if len(tokens) < 2 or not self.names:
            return None
        hits = process.extract(
            ngram, self.names, scorer=fuzz.token_set_ratio, processor=default_process,
            score_cutoff=FUZZY_CUTOFF, limit=None,
        )
        for _name, _score, idx in hits:
            if len(tokens & self.name_tokens[idx]) >= 2:
                return self.names[idx]
        return None


def _capitalised_runs(masked: str) -> list[list[str]]:
    """Runs of consecutive capitalised words separated only by whitespace."""
    runs: list[list[str]] = []
    current: list[str] = []
    last_end = -1
    for m in _CAP_WORD_RE.finditer(masked):
        word = m.group(0)
        if not word[0].isupper():
            if current:
                runs.append(current)
            current, last_end = [], -1
            continue
        if current and not (masked[last_end : m.start()].isspace()):
            runs.append(current)
            current = []
        current.append(word)
        last_end = m.end()
    if current:
        runs.append(current)
    return [r for r in runs if len(r) >= 2]


def _scan_sentence(
    masked: str,
    placeholder_ids: list[str],
    facts: Mapping[str, Mapping[str, Any]],
    bands: Mapping[str, str],
    entities: _EntityIndex,
    report: Callable[[str, str], None],
) -> None:
    """Rules 5 to 9 on one masked sentence."""
    for m in _NUMBER_RE.finditer(masked):
        report("literal_number", m.group(0))
    for code, rx in LEXICON.items():
        for m in rx.finditer(masked):
            report(code, m.group(0))

    if not any(pid.endswith(".band") and pid in bands for pid in placeholder_ids):
        for m in _QUALIFIER_RE.finditer(masked):
            report("ungrounded_qualifier", m.group(0))

    tokens = _TOKEN_RE.findall(masked)
    signed: list[tuple[int, str]] = []
    ph_iter = iter(placeholder_ids)
    for i, tok in enumerate(tokens):
        if tok == _P:
            fact = facts.get(next(ph_iter, ""))
            if fact is not None and fact.get("signed"):
                signed.append((i, str(fact.get("sign"))))
    for i, tok in enumerate(tokens):
        word = tok.lower()
        if word not in _UP_WORDS and word not in _DOWN_WORDS:
            continue
        want = "+" if word in _UP_WORDS else "-"
        near = {sign for pos, sign in signed if abs(pos - i) <= DIRECTION_WINDOW}
        if not near:
            report("ungrounded_direction", tok)
        elif want not in near:
            report("direction_mismatch", tok)

    for m in _UPPER_TOKEN_RE.finditer(masked):
        tok = m.group(0).rstrip("&-")
        if tok in entities.symbols and tok not in ENTITY_WHITELIST:
            report("foreign_entity", tok)
    for run in _capitalised_runs(masked):
        found = None
        for n in range(min(5, len(run)), 1, -1):
            for start in range(len(run) - n + 1):
                found = entities.fuzzy_match(" ".join(run[start : start + n]))
                if found:
                    break
            if found:
                break
        if found:
            report("foreign_entity", found)


def validate(
    raw: str | Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    known_symbols: Iterable[str],
    company_names: Iterable[str],
) -> ValidationResult:
    """Validate LLM (or template) output against the facts payload.

    ``raw`` is the model's text (one JSON object, optionally inside a single
    code fence) or an already-parsed dict. ``known_symbols`` are normalised
    tickers and ``company_names`` other companies' names, from
    ``research_repo.known_symbols_and_names(exclude_symbol=report.symbol)``.
    Failures are ``{code, field, sentence_idx, token}``; ``rendered`` is the
    substituted text whenever the shape is valid (stored only if ``passed``).
    """
    failures: list[dict[str, Any]] = []

    def fail(code: str, fname: str | None = None, idx: int | None = None, token: str | None = None) -> None:
        failures.append({"code": code, "field": fname, "sentence_idx": idx, "token": token})

    obj = _parse(raw, fail)
    if obj is None:
        return ValidationResult(False, failures, None)

    facts: dict[str, Mapping[str, Any]] = {f["id"]: f for f in payload.get("facts", [])}
    bands: Mapping[str, str] = payload.get("bands", {})
    known = set(facts) | set(bands) | {"as_of"}
    mask_re = _mask_pattern(payload)
    entities = _EntityIndex(payload, known_symbols, company_names)
    texts = {"summary": obj["summary"], **obj["sections"]}
    summary_placeholders = 0
    risk_used = False

    for fname in FIELDS:
        text: str = texts[fname]
        if len(text) > MAX_CHARS[fname]:
            fail("structure", fname, token=f"chars>{MAX_CHARS[fname]}")
        _check_format(text, fname, fail)
        sentences = [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s]
        if len(sentences) > MAX_SENTENCES:
            fail("structure", fname, token=f"sentences>{MAX_SENTENCES}")
        for idx, sentence in enumerate(sentences):
            ids = PLACEHOLDER_RE.findall(sentence)
            if len(PLACEHOLDER_RE.sub("P", sentence).split()) > MAX_WORDS:
                fail("structure", fname, idx, f"words>{MAX_WORDS}")
            for pid in ids:
                if pid not in known:
                    fail("unknown_placeholder", fname, idx, pid)
                    continue
                if fname == "summary":
                    summary_placeholders += 1
                elif not pid.startswith(SECTION_PREFIX[fname]):
                    fail("section_mismatch", fname, idx, pid)
                elif fname == "risk":
                    risk_used = True
            masked = PLACEHOLDER_RE.sub(_P, sentence)
            if mask_re is not None:
                masked = mask_re.sub(_M, masked)

            def report(code: str, token: str, _f: str = fname, _i: int = idx) -> None:
                fail(code, _f, _i, token)

            _scan_sentence(masked, ids, facts, bands, entities, report)

    if summary_placeholders == 0:
        fail("missing_required_fact", "summary")
    if not risk_used and any(fid.startswith("risk.") for fid in facts):
        fail("missing_required_fact", "risk")

    return ValidationResult(not failures, failures, render(obj, payload))
