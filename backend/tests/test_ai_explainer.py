"""Tests for the AI explanation layer.

These are the safety-boundary tests. They are the evidence for the claim that
AI cannot put medical advice in front of a patient, so they test the guard,
not the model.

None of them make a network call.
"""
import pytest

from app.services.ai_explainer import (
    AIExplainer,
    build_prompt,
    validate,
)


class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]


class FakeMessages:
    def __init__(self, text=None, error=None):
        self._text = text
        self._error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return FakeResponse(self._text)


class FakeClient:
    def __init__(self, text=None, error=None):
        self.messages = FakeMessages(text, error)


GOOD = (
    "These two medicines can both make bleeding more likely. Taken together "
    "that effect can be stronger. Please contact your pharmacist or healthcare "
    "provider to talk about it."
)


# ------------------------------------------------------- the guard itself

def test_a_good_explanation_passes():
    ok, reason = validate(GOOD)
    assert ok and reason is None


@pytest.mark.parametrize("bad", [
    "You should stop taking warfarin right away. Contact your pharmacist.",
    "Stop taking one of these medicines. Ask your doctor.",
    "You should reduce your dose. Speak to your pharmacist.",
    "Discontinue the aspirin and contact your healthcare provider.",
    "You may have a bleeding disorder. See your doctor.",
    "This is dangerous for you. Call your pharmacist.",
    "Skip a dose today, then call your pharmacist.",
    "Do not take these together. Ask your pharmacist.",
])
def test_advice_is_rejected(bad):
    """Each of these is something the system is forbidden to say. The prompt
    asks the model not to; this check guarantees it regardless."""
    ok, reason = validate(bad)
    assert not ok
    assert reason


def test_explanation_without_a_referral_is_rejected():
    """Every explanation must point the reader at a professional."""
    ok, reason = validate("These two medicines can interact with each other.")
    assert not ok
    assert "professional" in reason


def test_empty_response_is_rejected():
    assert validate("")[0] is False
    assert validate("   ")[0] is False


def test_overlong_response_is_rejected():
    assert validate("Contact your pharmacist. " * 100)[0] is False


# ----------------------------------------------------------- no patient data

def test_the_prompt_contains_no_patient_information():
    """The model receives a drug-safety fact and nothing that identifies a
    person. This is privacy by construction, not by policy."""
    prompt = build_prompt(
        title="Potential interaction: Acetylsalicylic acid and Warfarin",
        detail="DDInter records a potential interaction, rated Major.",
        source_name="DDInter",
        level="Major",
        drug_a="aspirin",
        drug_b="warfarin",
    )
    lowered = prompt.lower()
    for leak in ["maria", "santos", "patient_id", "@example.com", "date of birth", "uuid"]:
        assert leak not in lowered


# ------------------------------------------------------------ the pipeline

def test_a_valid_response_is_returned():
    explainer = AIExplainer(client=FakeClient(text=GOOD))
    result = explainer.explain(
        title="t", detail="d", source_name="DDInter", level="Major",
        drug_a="aspirin", drug_b="warfarin",
    )
    assert result.status == "ok"
    assert result.usable
    assert result.text == GOOD


def test_an_unsafe_response_is_discarded_not_stored():
    """The model said something forbidden. The patient must never see it, and
    the finding keeps its original wording."""
    explainer = AIExplainer(client=FakeClient(text="You should stop taking warfarin. Call your pharmacist."))
    result = explainer.explain(title="t", detail="d", source_name="DDInter")

    assert result.status == "rejected"
    assert result.text is None


def test_an_api_failure_degrades_quietly():
    """The AI being down must never break a finding."""
    explainer = AIExplainer(client=FakeClient(error=RuntimeError("API is down")))
    result = explainer.explain(title="t", detail="d", source_name="DDInter")

    assert result.status == "unavailable"
    assert result.text is None


def test_no_api_key_is_a_normal_state(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = AIExplainer().explain(title="t", detail="d", source_name="DDInter")

    assert result.status == "disabled"
    assert result.text is None


def test_the_system_prompt_forbids_the_right_things():
    client = FakeClient(text=GOOD)
    AIExplainer(client=client).explain(title="t", detail="d", source_name="DDInter")

    system = client.messages.calls[0]["system"].lower()
    for rule in ["never", "stop", "diagnose", "pharmacist"]:
        assert rule in system
