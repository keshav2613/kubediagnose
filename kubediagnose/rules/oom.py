from dataclasses import dataclass


@dataclass
class OOMFinding:
    detected: bool
    container: str | None = None
    restart_count: int = 0
    exit_code: int | None = None
    memory_limit: str | None = None


def analyze_oom(pod) -> OOMFinding:
    """Detect containers previously terminated because of OOMKilled."""

    statuses = pod.status.container_statuses or []

    for status in statuses:
        if not status.last_state:
            continue

        terminated = status.last_state.terminated

        if not terminated:
            continue

        if terminated.reason != "OOMKilled":
            continue

        memory_limit = None

        for container in pod.spec.containers:
            if container.name != status.name:
                continue

            if container.resources and container.resources.limits:
                memory_limit = container.resources.limits.get("memory")

            break

        return OOMFinding(
            detected=True,
            container=status.name,
            restart_count=status.restart_count or 0,
            exit_code=terminated.exit_code,
            memory_limit=memory_limit,
        )

    return OOMFinding(detected=False)