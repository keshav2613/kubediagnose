from types import SimpleNamespace

from kubediagnose.rules.imagepull import analyze_imagepull


def make_pod(reason=None, message=None):
    waiting = (
        SimpleNamespace(
            reason=reason,
            message=message,
        )
        if reason
        else None
    )

    status = SimpleNamespace(
        name="demo-container",
        image="example/demo:v999",
        state=SimpleNamespace(
            waiting=waiting
        ),
    )

    return SimpleNamespace(
        status=SimpleNamespace(
            container_statuses=[status]
        )
    )


def test_detects_imagepullbackoff():
    pod = make_pod(
        reason="ImagePullBackOff",
        message="Back-off pulling image",
    )

    finding = analyze_imagepull(pod)

    assert finding.detected is True
    assert finding.container == "demo-container"
    assert finding.image == "example/demo:v999"
    assert finding.reason == "ImagePullBackOff"


def test_detects_errimagepull():
    pod = make_pod(
        reason="ErrImagePull",
        message="Failed to pull image",
    )

    finding = analyze_imagepull(pod)

    assert finding.detected is True
    assert finding.reason == "ErrImagePull"


def test_running_container_not_detected():
    pod = make_pod()

    finding = analyze_imagepull(pod)

    assert finding.detected is False