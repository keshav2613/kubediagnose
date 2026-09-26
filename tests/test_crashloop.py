from types import SimpleNamespace

from kubediagnose.rules.crashloop import analyze_crashloop


def make_pod(
    waiting_reason=None,
    last_reason=None,
    exit_code=None,
    restart_count=0,
):
    waiting = (
        SimpleNamespace(reason=waiting_reason)
        if waiting_reason
        else None
    )

    terminated = (
        SimpleNamespace(
            reason=last_reason,
            exit_code=exit_code,
        )
        if last_reason is not None
        else None
    )

    status = SimpleNamespace(
        name="demo-container",
        restart_count=restart_count,
        state=SimpleNamespace(waiting=waiting),
        last_state=SimpleNamespace(terminated=terminated),
    )

    return SimpleNamespace(
        status=SimpleNamespace(
            container_statuses=[status]
        )
    )


def test_detects_crashloopbackoff():
    pod = make_pod(
        waiting_reason="CrashLoopBackOff",
        last_reason="Error",
        exit_code=1,
        restart_count=5,
    )

    finding = analyze_crashloop(pod)

    assert finding.detected is True
    assert finding.container == "demo-container"
    assert finding.restart_count == 5
    assert finding.reason == "CrashLoopBackOff"
    assert finding.last_reason == "Error"
    assert finding.exit_code == 1


def test_detects_repeated_container_failure():
    pod = make_pod(
        last_reason="Error",
        exit_code=1,
        restart_count=3,
    )

    finding = analyze_crashloop(pod)

    assert finding.detected is True
    assert finding.reason == "RepeatedContainerFailure"


def test_healthy_container_not_detected():
    pod = make_pod(
        restart_count=0,
    )

    finding = analyze_crashloop(pod)

    assert finding.detected is False