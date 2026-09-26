from types import SimpleNamespace

from kubediagnose.rules.scheduling import analyze_scheduling


def make_pod(
    phase="Pending",
    scheduled_status="False",
    reason="Unschedulable",
):
    condition = SimpleNamespace(
        type="PodScheduled",
        status=scheduled_status,
        reason=reason,
        message="0/1 nodes are available: 1 Insufficient memory.",
    )

    return SimpleNamespace(
        status=SimpleNamespace(
            phase=phase,
            conditions=[condition],
        )
    )


def test_detects_failed_scheduling():
    pod = make_pod()

    finding = analyze_scheduling(pod)

    assert finding.detected is True
    assert finding.reason == "Unschedulable"
    assert "Insufficient memory" in finding.message


def test_running_pod_not_detected():
    pod = make_pod(
        phase="Running",
    )

    finding = analyze_scheduling(pod)

    assert finding.detected is False


def test_pending_but_scheduled_pod_not_detected():
    pod = make_pod(
        scheduled_status="True",
        reason=None,
    )

    finding = analyze_scheduling(pod)

    assert finding.detected is False