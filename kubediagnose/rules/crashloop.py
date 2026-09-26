from dataclasses import dataclass


@dataclass
class CrashLoopFinding:
    detected: bool
    container: str | None = None
    restart_count: int = 0
    reason: str | None = None
    exit_code: int | None = None
    last_reason: str | None = None


def analyze_crashloop(pod) -> CrashLoopFinding:
    """
    Detect containers that are currently in CrashLoopBackOff.

    Kubernetes may report the overall Pod phase as Running even when
    an individual container is waiting in CrashLoopBackOff, so we
    inspect containerStatuses instead of relying on pod.status.phase.
    """

    statuses = pod.status.container_statuses or []

    for status in statuses:
        waiting = None
        terminated = None

        if status.state:
            waiting = status.state.waiting

        if status.last_state:
            terminated = status.last_state.terminated

        waiting_reason = waiting.reason if waiting else None
        last_reason = terminated.reason if terminated else None
        exit_code = terminated.exit_code if terminated else None

        # Primary signal: Kubernetes explicitly reports CrashLoopBackOff
        if waiting_reason == "CrashLoopBackOff":
            return CrashLoopFinding(
                detected=True,
                container=status.name,
                restart_count=status.restart_count or 0,
                reason=waiting_reason,
                exit_code=exit_code,
                last_reason=last_reason,
            )

        # Secondary signal:
        # The CLI may query during the brief period where the container
        # has restarted and is no longer in the waiting state.
        if (
            (status.restart_count or 0) >= 2
            and terminated is not None
            and exit_code not in (None, 0)
        ):
            return CrashLoopFinding(
                detected=True,
                container=status.name,
                restart_count=status.restart_count or 0,
                reason="RepeatedContainerFailure",
                exit_code=exit_code,
                last_reason=last_reason,
            )

    return CrashLoopFinding(detected=False)