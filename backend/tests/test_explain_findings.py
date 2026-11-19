"""Tests for attaching explanations to stored findings."""
from datetime import datetime, timezone

from app.models.enums import FindingStatus, FindingType, Severity
from app.models.safety import SafetyFinding
from app.services.ai_explainer import AIExplainer, ExplanationResult
from app.services.explain_findings import explain_pending


class StubExplainer(AIExplainer):
    def __init__(self, result: ExplanationResult):
        super().__init__(client=object())
        self._result = result

    def explain(self, **kwargs):
        return self._result


def make_finding(db, patient, **kwargs):
    defaults = dict(
        patient_id=patient.id,
        finding_type=FindingType.INTERACTION,
        severity=Severity.SEVERE,
        status=FindingStatus.OPEN,
        title="Potential interaction",
        detail="DDInter records a potential interaction, rated Major.",
        source_name="DDInter",
        source_version="2.0",
        dedupe_key=f"key-{kwargs.get('n', 1)}",
        detected_at=datetime.now(timezone.utc),
    )
    defaults.pop("n", None)
    defaults.update({k: v for k, v in kwargs.items() if k != "n"})
    f = SafetyFinding(**defaults)
    db.add(f)
    db.flush()
    return f


GOOD = (
    "These two medicines can both make bleeding more likely. Contact your "
    "pharmacist or healthcare provider."
)


def test_a_valid_explanation_is_saved(db, patient):
    finding = make_finding(db, patient)
    result = explain_pending(db, explainer=StubExplainer(ExplanationResult(GOOD, "ok")))

    assert result["ok"] == 1
    assert finding.ai_explanation == GOOD
    assert finding.ai_model
    assert finding.ai_generated_at is not None


def test_a_rejected_explanation_leaves_the_finding_untouched(db, patient):
    """The finding must still be complete and displayable."""
    finding = make_finding(db, patient)
    explain_pending(db, explainer=StubExplainer(ExplanationResult(None, "rejected", "forbidden advice")))

    assert finding.ai_explanation is None
    assert finding.detail                 # the finding still stands on its own


def test_an_unavailable_service_leaves_the_finding_untouched(db, patient):
    finding = make_finding(db, patient)
    explain_pending(db, explainer=StubExplainer(ExplanationResult(None, "unavailable", "timeout")))

    assert finding.ai_explanation is None


def test_findings_that_already_have_an_explanation_are_skipped(db, patient):
    """We do not pay to re-explain the same finding on every worker run."""
    make_finding(db, patient, ai_explanation="already done")
    result = explain_pending(db, explainer=StubExplainer(ExplanationResult(GOOD, "ok")))

    assert result["examined"] == 0
