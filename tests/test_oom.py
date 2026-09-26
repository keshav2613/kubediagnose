from types import SimpleNamespace

from kubediagnose.rules.oom import analyze_oom


def make_pod(
    termination_reason="OOMKilled",
    exit_code=137,
    restart_count=3,
):
    terminated = SimpleNamespace(
        reason=termination_reason,
        exit_code=exit_code,
    )

    container_status = SimpleNamespace(
        name="memory-demo",
        restart_count=restart_count,
        last_state=SimpleNamespace(
            terminated=terminated
        ),
    )

    container_spec = SimpleNamespace(
        name="memory-demo",
        resources=SimpleNamespace(
            limits={
                "memory": "32Mi"
            }
        ),
    )

    return SimpleNamespace(
        status=SimpleNamespace(
            container_statuses=[container_status]
        ),
        spec=SimpleNamespace(
            containers=[container_spec]
        ),
    )


def test_detects_oomkilled():
    pod = make_pod()

    finding = analyze_oom(pod)

    assert finding.detected is True
    assert finding.container == "memory-demo"
    assert finding.restart_count == 3
    assert finding.exit_code == 137
    assert finding.memory_limit == "32Mi"


def test_normal_termination_not_detected():
    pod = make_pod(
        termination_reason="Completed",
        exit_code=0,
    )

    finding = analyze_oom(pod)

    assert finding.detected is False