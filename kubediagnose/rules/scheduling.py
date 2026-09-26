from dataclasses import dataclass


@dataclass
class SchedulingFinding:
    detected: bool
    reason: str | None = None
    message: str | None = None


def analyze_scheduling(pod) -> SchedulingFinding:
    """
    Detect pods that Kubernetes cannot schedule onto a node.

    We inspect the PodScheduled condition instead of assuming
    that every Pending pod has a scheduling problem.
    """

    if pod.status.phase != "Pending":
        return SchedulingFinding(detected=False)

    conditions = pod.status.conditions or []

    for condition in conditions:
        if (
            condition.type == "PodScheduled"
            and condition.status == "False"
            and condition.reason == "Unschedulable"
        ):
            return SchedulingFinding(
                detected=True,
                reason=condition.reason,
                message=condition.message,
            )

    return SchedulingFinding(detected=False)