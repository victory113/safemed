"""Plain-language explanations of verified safety findings.

WHERE THIS SITS IN THE SYSTEM
-----------------------------
At the very end, and strictly off the safety path.

By the time this code runs, the finding already exists: the deterministic
engine decided an interaction is real, assigned a severity from the source
data, and stored it with its provenance. Nothing here can create a finding,
change a severity, or decide that something is safe.

Its one job is translation - turning

    "DDInter records a potential interaction between Acetylsalicylic acid and
     Warfarin, rated Major."

into something a worried 70-year-old can actually act on.

THREE LAYERS OF PROTECTION
--------------------------
1. The model is never asked to make a judgement. It receives a finished
   finding and is asked to rephrase it.
2. No patient data is sent. Not a name, not an id, not a date of birth - only
   the drug names and the source's own description.
3. Every response is validated before it is stored. If it contains advice we
   have forbidden, it is discarded and the original text is kept.

Layer 3 is the important one. A system prompt is a request; validation is a
guarantee. We assume the prompt can fail and check anyway.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
MAX_TOKENS = 600

SYSTEM_PROMPT = """You rewrite medication safety findings into plain language for patients and their caregivers.

You are given a finding that has ALREADY been verified against an authoritative drug-safety database. Your only job is to make it easier to understand.

You MUST:
- Write at roughly a 6th-grade reading level, in short sentences.
- Explain what the two medicines are commonly used for, and what the concern is.
- Keep every fact from the finding. Do not add facts of your own.
- End by telling the reader to contact their pharmacist or healthcare provider.

You MUST NEVER:
- Tell anyone to stop, start, pause, skip, reduce, increase or change any medication or dose.
- Diagnose a condition or suggest what might be wrong with the reader.
- Say a medication is safe, unsafe, dangerous, or harmful for this person.
- Invent an interaction, a severity, a statistic or a source that is not in the finding you were given.
- Give an opinion about whether the reader should be worried.

Write 2 to 4 short sentences. Plain text only, no markdown, no headings."""

# Phrases that mean the model has strayed into advice. Matched case-insensitively
# against the whole response. Deliberately blunt: a false rejection costs us a
# nicer wording, a false acceptance costs a patient the wrong instruction.
FORBIDDEN_PATTERNS = [
    r"\bstop (taking|using)\b",
    r"\b(you|patients?) should (stop|start|discontinue|reduce|increase|avoid|switch)\b",
    r"\bdiscontinue\b",
    r"\bskip (a|your|the) (dose|medication)\b",
    r"\b(increase|decrease|reduce|lower|raise|adjust|change) (your|the) dos",
    r"\bdo not take\b",
    r"\bstop immediately\b",
    r"\byou (have|may have|might have|are suffering)\b",
    r"\b(this|it) is (safe|unsafe|dangerous|harmful) for you\b",
    r"\bi diagnose\b",
    r"\byou don'?t need\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]

# A valid explanation must point the reader at a professional.
REQUIRED_PATTERN = re.compile(r"pharmacist|healthcare provider|doctor", re.IGNORECASE)


@dataclass(frozen=True)
class ExplanationResult:
    text: str | None
    status: str          # "ok" | "rejected" | "unavailable" | "disabled"
    reason: str | None = None

    @property
    def usable(self) -> bool:
        return self.text is not None


def validate(text: str) -> tuple[bool, str | None]:
    """Check a generated explanation before it is allowed near a patient.

    This runs on every response, including ones that look fine. It is the
    difference between hoping the model behaved and knowing it did.
    """
    if not text or not text.strip():
        return False, "empty response"

    for pattern in _COMPILED:
        match = pattern.search(text)
        if match:
            return False, f"forbidden advice: {match.group(0)!r}"

    if not REQUIRED_PATTERN.search(text):
        return False, "does not direct the reader to a professional"

    if len(text) > 1200:
        return False, "too long"

    return True, None


def build_prompt(
    title: str, detail: str, source_name: str, level: str | None,
    drug_a: str | None, drug_b: str | None,
) -> str:
    """Assemble what the model sees.

    Note what is absent: no patient name, no id, no age, no medication list,
    no dates. The model is given a drug-safety fact and nothing that could
    identify a person.
    """
    lines = [
        "Rewrite this verified safety finding in plain language.",
        "",
        f"Finding: {title}",
        f"Details: {detail}",
        f"Source: {source_name}",
    ]
    if level:
        lines.append(f"Severity recorded by the source: {level}")
    if drug_a and drug_b:
        lines.append(f"Medicines involved: {drug_a} and {drug_b}")
    return "\n".join(lines)


class AIExplainer:
    """Wraps the Claude API with our guardrails.

    `client` is injectable so tests never make a network call.
    """

    def __init__(self, client=None, model: str = MODEL) -> None:
        self._client = client
        self._model = model
        self._explicit_client = client is not None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic package is not installed")
            return None
        self._client = anthropic.Anthropic()
        return self._client

    def explain(
        self, *, title: str, detail: str, source_name: str,
        level: str | None = None, drug_a: str | None = None,
        drug_b: str | None = None,
    ) -> ExplanationResult:
        client = self._get_client()
        if client is None:
            # No key configured. Entirely normal - the finding displays its
            # own text and nothing is lost.
            return ExplanationResult(None, "disabled", "no API key configured")

        prompt = build_prompt(title, detail, source_name, level, drug_a, drug_b)

        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - any failure degrades the same way
            logger.warning("AI explanation failed: %s: %s", type(exc).__name__, exc)
            return ExplanationResult(None, "unavailable", str(exc)[:200])

        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip()

        ok, reason = validate(text)
        if not ok:
            # The model produced something we will not show. The finding keeps
            # its original wording; nobody sees this text.
            logger.warning("AI explanation rejected (%s)", reason)
            return ExplanationResult(None, "rejected", reason)

        return ExplanationResult(text, "ok")
