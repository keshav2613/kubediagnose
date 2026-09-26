from types import SimpleNamespace
from unittest.mock import Mock

from kubediagnose.engine import DiagnosticEngine


def make_pod(
    *,
    phase="Running",
    waiting_reason=None,
    waiting_message=None,
    last_reason=None,
    exit_code=None,
    restart_count=0,
    scheduled_status="True",
    scheduled_reason=None,
):
    """Create a lightweight mock Kubernetes pod."""

    waiting = None

    if waiting_reason:
        waiting = SimpleNamespace(
            reason=waiting_reason,
            message=waiting_message,
        )

    terminated = None

    if last_reason:
        terminated = SimpleNamespace(
            reason=last_reason,
            exit_code=exit_code,
        )

    container_status = SimpleNamespace(
        name="demo-container",
        image="example/demo:latest",
        restart_count=restart_count,
        state=SimpleNamespace(
            waiting=waiting,
        ),
        last_state=SimpleNamespace(
            terminated=terminated,
        ),
    )

    container_spec = SimpleNamespace(
        name="demo-container",
        resources=SimpleNamespace(
            limits={
                "memory": "32Mi",
            }
        ),
    )

    condition = SimpleNamespace(
        type="PodScheduled",
        status=scheduled_status,
        reason=scheduled_reason,
        message="Scheduling failure",
    )

    return SimpleNamespace(
        metadata=SimpleNamespace(
            name="demo-pod",
        ),
        status=SimpleNamespace(
            phase=phase,
            container_statuses=[
                container_status,
            ],
            conditions=[
                condition,
            ],
        ),
        spec=SimpleNamespace(
            containers=[
                container_spec,
            ]
        ),
    )


def make_engine(events=None):
    """Create an engine with a mocked Kubernetes client."""

    k8s = Mock()

    k8s.get_pod_events.return_value = events or []

    return DiagnosticEngine(k8s), k8s


def test_engine_detects_failed_scheduling():
    engine, k8s = make_engine()

    pod = make_pod(
        phase="Pending",
        scheduled_status="False",
        scheduled_reason="Unschedulable",
    )

    result = engine.diagnose_pod(
        pod,
        namespace="default",
    )

    assert result is not None
    assert result.kind == "scheduling"

    k8s.get_pod_events.assert_called_once_with(
        pod_name="demo-pod",
        namespace="default",
    )


def test_engine_detects_image_pull():
    engine, _ = make_engine()

    pod = make_pod(
        phase="Pending",
        waiting_reason="ImagePullBackOff",
        waiting_message="Back-off pulling image",
    )

    result = engine.diagnose_pod(
        pod,
        namespace="default",
    )

    assert result is not None
    assert result.kind == "imagepull"


def test_engine_detects_oom():
    engine, _ = make_engine()

    pod = make_pod(
        waiting_reason="CrashLoopBackOff",
        last_reason="OOMKilled",
        exit_code=137,
        restart_count=4,
    )

    result = engine.diagnose_pod(
        pod,
        namespace="default",
    )

    assert result is not None
    assert result.kind == "oom"
    assert result.finding.exit_code == 137


def test_oom_has_priority_over_crashloop():
    engine, _ = make_engine()

    # Kubernetes can report CrashLoopBackOff as the current
    # state while the previous termination was OOMKilled.
    pod = make_pod(
        waiting_reason="CrashLoopBackOff",
        last_reason="OOMKilled",
        exit_code=137,
        restart_count=5,
    )

    result = engine.diagnose_pod(
        pod,
        namespace="default",
    )

    assert result is not None

    # Root cause should win over generic symptom.
    assert result.kind == "oom"


def test_engine_detects_readiness_probe_failure():
    event = SimpleNamespace(
        reason="Unhealthy",
        message=(
            "Readiness probe failed: "
            "HTTP probe failed with statuscode: 404"
        ),
    )

    engine, _ = make_engine(
        events=[event]
    )

    pod = make_pod()

    result = engine.diagnose_pod(
        pod,
        namespace="default",
    )

    assert result is not None
    assert result.kind == "probe"
    assert result.finding.probe_type == "Readiness"


def test_engine_detects_crashloop():
    engine, _ = make_engine()

    pod = make_pod(
        waiting_reason="CrashLoopBackOff",
        last_reason="Error",
        exit_code=1,
        restart_count=4,
    )

    result = engine.diagnose_pod(
        pod,
        namespace="default",
    )

    assert result is not None
    assert result.kind == "crashloop"


def test_engine_returns_none_for_healthy_pod():
    engine, _ = make_engine()

    pod = make_pod()

    result = engine.diagnose_pod(
        pod,
        namespace="default",
    )

    assert result is None


def test_diagnose_pods_returns_first_failure():
    engine, _ = make_engine()

    healthy_pod = make_pod()

    failing_pod = make_pod(
        waiting_reason="ImagePullBackOff",
        waiting_message="Back-off pulling image",
    )

    failing_pod.metadata.name = "failing-pod"

    result = engine.diagnose_pods(
        pods=[
            healthy_pod,
            failing_pod,
        ],
        namespace="default",
    )

    assert result is not None
    assert result.kind == "imagepull"
    assert result.pod.metadata.name == "failing-pod"