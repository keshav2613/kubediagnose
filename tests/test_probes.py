from types import SimpleNamespace

from kubediagnose.rules.probes import analyze_probe_failure


def make_event(reason, message):
    return SimpleNamespace(
        reason=reason,
        message=message,
    )


def test_detects_readiness_probe_failure():
    pod = SimpleNamespace()

    events = [
        make_event(
            "Unhealthy",
            "Readiness probe failed: HTTP probe failed "
            "with statuscode: 404",
        )
    ]

    finding = analyze_probe_failure(
        pod,
        events,
    )

    assert finding.detected is True
    assert finding.probe_type == "Readiness"
    assert "404" in finding.message


def test_detects_liveness_probe_failure():
    pod = SimpleNamespace()

    events = [
        make_event(
            "Unhealthy",
            "Liveness probe failed: connection refused",
        )
    ]

    finding = analyze_probe_failure(
        pod,
        events,
    )

    assert finding.detected is True
    assert finding.probe_type == "Liveness"


def test_unrelated_event_not_detected():
    pod = SimpleNamespace()

    events = [
        make_event(
            "Pulled",
            "Successfully pulled image",
        )
    ]

    finding = analyze_probe_failure(
        pod,
        events,
    )

    assert finding.detected is False