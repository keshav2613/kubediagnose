from dataclasses import dataclass


@dataclass
class ProbeFinding:
    detected: bool
    probe_type: str | None = None
    message: str | None = None


def analyze_probe_failure(pod, events) -> ProbeFinding:
    """Detect readiness or liveness probe failures from pod events."""

    for event in reversed(events):
        if event.reason != "Unhealthy":
            continue

        message = event.message or ""
        message_lower = message.lower()

        if "readiness probe failed" in message_lower:
            return ProbeFinding(
                detected=True,
                probe_type="Readiness",
                message=message,
            )

        if "liveness probe failed" in message_lower:
            return ProbeFinding(
                detected=True,
                probe_type="Liveness",
                message=message,
            )

    return ProbeFinding(detected=False)