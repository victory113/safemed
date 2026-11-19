"""Tests for RxNorm normalization.

None of these touch the network. Each supplies a fake transport that returns
a canned response, so the suite is fast, deterministic, and passes on a train.

The failure tests matter most: they prove that RxNorm being unavailable never
stops a medication being recorded.
"""
import httpx
import pytest

from app.services.rxnorm import RxNormClient


def make_client(handler) -> RxNormClient:
    """Build an RxNormClient whose HTTP calls are answered by `handler`."""
    transport = httpx.MockTransport(handler)
    return RxNormClient(client=httpx.Client(transport=transport), timeout=2.0)


# --------------------------------------------------------------- happy path

def test_exact_match_returns_rxcui_and_canonical_name():
    def handler(request: httpx.Request) -> httpx.Response:
        if "rxcui.json" in request.url.path:
            return httpx.Response(200, json={"idGroup": {"rxnormId": ["6809"]}})
        if "properties.json" in request.url.path:
            return httpx.Response(
                200, json={"properties": {"rxcui": "6809", "name": "metformin"}}
            )
        return httpx.Response(404)

    result = make_client(handler).normalize("Metformin")

    assert result.found
    assert result.rxcui == "6809"
    assert result.normalized_name == "metformin"
    assert result.matched_by == "exact"


def test_approximate_match_used_when_exact_fails():
    """A typo like 'metformin' should still resolve."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "rxcui.json" in request.url.path:
            return httpx.Response(200, json={"idGroup": {}})
        if "approximateTerm.json" in request.url.path:
            return httpx.Response(
                200,
                json={"approximateGroup": {"candidate": [{"rxcui": "6809", "score": "11.2"}]}},
            )
        if "properties.json" in request.url.path:
            return httpx.Response(200, json={"properties": {"name": "metformin"}})
        return httpx.Response(404)

    result = make_client(handler).normalize("metformin")

    assert result.rxcui == "6809"
    assert result.matched_by == "approximate"


# ------------------------------------------------------------- no match ----

def test_unrecognised_name_returns_no_match():
    def handler(request: httpx.Request) -> httpx.Response:
        if "rxcui.json" in request.url.path:
            return httpx.Response(200, json={"idGroup": {}})
        if "approximateTerm.json" in request.url.path:
            return httpx.Response(200, json={"approximateGroup": {}})
        return httpx.Response(404)

    result = make_client(handler).normalize("zzzznotadrug")

    assert not result.found
    assert result.rxcui is None
    assert result.matched_by == "none"


def test_low_scoring_approximate_match_is_rejected():
    """A wrong guess is worse than no guess - it would attach the patient's
    entry to a drug they do not take."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "rxcui.json" in request.url.path:
            return httpx.Response(200, json={"idGroup": {}})
        if "approximateTerm.json" in request.url.path:
            return httpx.Response(
                200,
                json={"approximateGroup": {"candidate": [{"rxcui": "999", "score": "2.0"}]}},
            )
        return httpx.Response(404)

    assert not make_client(handler).normalize("asprn").found


def test_empty_name_returns_no_match_without_calling_the_api():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json={})

    assert not make_client(handler).normalize("   ").found
    assert calls == []


# -------------------------------------------------- service unavailable ----

def test_timeout_returns_no_match_and_does_not_raise():
    """The core requirement: RxNorm being slow must never stop a medication
    being saved."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow", request=request)

    result = make_client(handler).normalize("Metformin")

    assert not result.found
    assert result.matched_by == "none"


def test_server_error_returns_no_match_and_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream exploded")

    assert not make_client(handler).normalize("Metformin").found


def test_malformed_json_returns_no_match_and_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    assert not make_client(handler).normalize("Metformin").found


def test_properties_failure_falls_back_to_the_entered_name():
    """We found an identifier but could not fetch the official name. Keep the
    identifier - it is the valuable part - and fall back to what the patient
    typed."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "rxcui.json" in request.url.path:
            return httpx.Response(200, json={"idGroup": {"rxnormId": ["6809"]}})
        return httpx.Response(503)

    result = make_client(handler).normalize("Metformin")

    assert result.rxcui == "6809"
    assert result.normalized_name == "Metformin"
