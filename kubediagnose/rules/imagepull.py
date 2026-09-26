from dataclasses import dataclass

IMAGE_PULL_REASONS = {
    "ErrImagePull",
    "ImagePullBackOff",
}


@dataclass
class ImagePullFinding:
    detected: bool
    container: str | None = None
    image: str | None = None
    reason: str | None = None
    message: str | None = None


def analyze_imagepull(pod) -> ImagePullFinding:
    """
    Detect container image pull failures.

    Kubernetes normally exposes image pull problems through
    containerStatuses.state.waiting.
    """

    statuses = pod.status.container_statuses or []

    for status in statuses:
        if not status.state:
            continue

        waiting = status.state.waiting

        if not waiting:
            continue

        if waiting.reason in IMAGE_PULL_REASONS:
            return ImagePullFinding(
                detected=True,
                container=status.name,
                image=status.image,
                reason=waiting.reason,
                message=waiting.message,
            )

    return ImagePullFinding(detected=False)