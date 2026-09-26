from dataclasses import dataclass
from typing import Any

from kubediagnose.rules.crashloop import analyze_crashloop
from kubediagnose.rules.imagepull import analyze_imagepull
from kubediagnose.rules.oom import analyze_oom
from kubediagnose.rules.probes import analyze_probe_failure
from kubediagnose.rules.scheduling import analyze_scheduling


@dataclass
class DiagnosticResult:
    """Result returned by the diagnostic engine."""

    kind: str
    pod: Any
    finding: Any
    events: list[Any] | None = None


class DiagnosticEngine:
    """Run diagnostic rules against Kubernetes pods."""

    def __init__(self, k8s_client):
        self.k8s = k8s_client

    def diagnose_pod(
        self,
        pod,
        namespace: str,
    ) -> DiagnosticResult | None:
        """
        Diagnose a single pod.

        Rules are evaluated in priority order so that specific
        root causes are preferred over more generic symptoms.
        """

        # 1. FailedScheduling
        finding = analyze_scheduling(pod)

        if finding.detected:
            events = self.k8s.get_pod_events(
                pod_name=pod.metadata.name,
                namespace=namespace,
            )

            return DiagnosticResult(
                kind="scheduling",
                pod=pod,
                finding=finding,
                events=events,
            )

        # 2. ImagePullBackOff / ErrImagePull
        finding = analyze_imagepull(pod)

        if finding.detected:
            events = self.k8s.get_pod_events(
                pod_name=pod.metadata.name,
                namespace=namespace,
            )

            return DiagnosticResult(
                kind="imagepull",
                pod=pod,
                finding=finding,
                events=events,
            )

        # 3. OOMKilled
        finding = analyze_oom(pod)

        if finding.detected:
            return DiagnosticResult(
                kind="oom",
                pod=pod,
                finding=finding,
            )

        # 4. Readiness / Liveness probe failure
        events = self.k8s.get_pod_events(
            pod_name=pod.metadata.name,
            namespace=namespace,
        )

        finding = analyze_probe_failure(
            pod,
            events,
        )

        if finding.detected:
            return DiagnosticResult(
                kind="probe",
                pod=pod,
                finding=finding,
                events=events,
            )

        # 5. CrashLoopBackOff
        finding = analyze_crashloop(pod)

        if finding.detected:
            return DiagnosticResult(
                kind="crashloop",
                pod=pod,
                finding=finding,
            )

        return None

    def diagnose_pods(
        self,
        pods,
        namespace: str,
    ) -> DiagnosticResult | None:
        """Return the first supported diagnosis found."""

        for pod in pods:
            result = self.diagnose_pod(
                pod=pod,
                namespace=namespace,
            )

            if result is not None:
                return result

        return None