import ast

import typer
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from rich.console import Console
from rich.panel import Panel

from kubediagnose.k8s_client import KubernetesClient
from kubediagnose.rules.crashloop import analyze_crashloop
from kubediagnose.rules.imagepull import analyze_imagepull
from kubediagnose.rules.oom import analyze_oom
from kubediagnose.rules.probes import analyze_probe_failure
from kubediagnose.rules.scheduling import analyze_scheduling

app = typer.Typer(
    help="Evidence-based Kubernetes workload diagnostics."
)

console = Console()


def normalize_logs(logs) -> str | None:
    """Normalize Kubernetes log output into a clean string."""

    if logs is None:
        return None

    if isinstance(logs, bytes):
        return logs.decode("utf-8", errors="replace")

    if isinstance(logs, str):
        # Handle strings that look like:
        # b'application failed\n'
        if logs.startswith("b'") and logs.endswith("'"):
            try:
                parsed = ast.literal_eval(logs)

                if isinstance(parsed, bytes):
                    return parsed.decode(
                        "utf-8",
                        errors="replace",
                    )

            except (ValueError, SyntaxError):
                pass

        return logs

    return str(logs)


@app.command()
def version():
    """Display the installed KubeDiagnose version."""

    console.print(
        Panel.fit(
            "[bold cyan]KubeDiagnose[/bold cyan]\n"
            "Version: 0.1.0",
            title="Kubernetes Diagnostics",
        )
    )


@app.command()
def diagnose(
    workload: str,
    namespace: str = typer.Option(
        "default",
        "--namespace",
        "-n",
        help="Kubernetes namespace",
    ),
):
    """Diagnose a Kubernetes deployment."""

    console.print()
    console.print("[bold cyan]KubeDiagnose[/bold cyan]")
    console.print("─" * 50)

    console.print(f"[bold]Workload:[/bold]  {workload}")
    console.print(f"[bold]Namespace:[/bold] {namespace}")
    console.print()

    try:
        # =========================================================
        # CONNECT TO KUBERNETES
        # =========================================================

        k8s = KubernetesClient()

        # =========================================================
        # FIND DEPLOYMENT
        # =========================================================

        deployment = k8s.get_deployment(
            name=workload,
            namespace=namespace,
        )

        if deployment is None:
            console.print(
                f"[red]✗ Deployment '{workload}' was not found "
                f"in namespace '{namespace}'.[/red]"
            )
            raise typer.Exit(code=1)

        # =========================================================
        # FIND PODS
        # =========================================================

        pods = k8s.get_deployment_pods(
            deployment=deployment,
            namespace=namespace,
        )

        console.print(
            "[green]✓ Connected to Kubernetes API[/green]"
        )

        desired_replicas = deployment.spec.replicas or 0
        ready_replicas = deployment.status.ready_replicas or 0

        console.print(
            f"[bold]Deployment replicas:[/bold] "
            f"{ready_replicas}/{desired_replicas}"
        )

        # =========================================================
        # DISPLAY PODS
        # =========================================================

        console.print()
        console.print("[bold]Pods[/bold]")

        if not pods:
            console.print(
                "[yellow]No pods found for this deployment.[/yellow]"
            )
            return

        for pod in pods:
            console.print(
                f"  {pod.metadata.name:<45} "
                f"{pod.status.phase}"
            )

        # =========================================================
        # DIAGNOSTIC ENGINE
        #
        # Priority:
        # 1. FailedScheduling
        # 2. ImagePullBackOff
        # 3. OOMKilled
        # 4. Probe failure
        # 5. CrashLoopBackOff
        # =========================================================

        for pod in pods:

            # =====================================================
            # RULE 1 — FAILED SCHEDULING
            # =====================================================

            scheduling_finding = analyze_scheduling(pod)

            if scheduling_finding.detected:
                console.print()
                console.print(
                    "[bold red]✗ FailedScheduling detected[/bold red]"
                )

                console.print()
                console.print("[bold]Evidence[/bold]")

                console.print(
                    f"Pod:       {pod.metadata.name}"
                )

                console.print(
                    f"Phase:     {pod.status.phase}"
                )

                console.print(
                    "Scheduled: False"
                )

                console.print(
                    f"Reason:    {scheduling_finding.reason}"
                )

                if scheduling_finding.message:
                    console.print()
                    console.print(
                        "[bold]Scheduler message[/bold]"
                    )
                    console.print(
                        scheduling_finding.message
                    )

                events = k8s.get_pod_events(
                    pod_name=pod.metadata.name,
                    namespace=namespace,
                )

                failed_scheduling_events = [
                    event
                    for event in events
                    if event.reason == "FailedScheduling"
                ]

                if failed_scheduling_events:
                    console.print()
                    console.print(
                        "[bold]Kubernetes events[/bold]"
                    )

                    for event in failed_scheduling_events[-5:]:
                        console.print(
                            f"• {event.reason}: "
                            f"{event.message}"
                        )

                console.print()
                console.print("[bold]Diagnosis[/bold]")

                console.print(
                    "Kubernetes cannot find a node that satisfies "
                    "the workload's scheduling requirements."
                )

                console.print()
                console.print(
                    "[bold]Recommended checks[/bold]"
                )

                console.print(
                    "1. Review CPU and memory requests."
                )
                console.print(
                    "2. Check available node capacity."
                )
                console.print(
                    "3. Review node selectors and affinity rules."
                )
                console.print(
                    "4. Check node taints and pod tolerations."
                )

                return

            # =====================================================
            # RULE 2 — IMAGE PULL FAILURE
            # =====================================================

            image_finding = analyze_imagepull(pod)

            if image_finding.detected:
                console.print()
                console.print(
                    f"[bold red]✗ "
                    f"{image_finding.reason} detected"
                    f"[/bold red]"
                )

                console.print()
                console.print("[bold]Evidence[/bold]")

                console.print(
                    f"Pod:       {pod.metadata.name}"
                )
                console.print(
                    f"Container: {image_finding.container}"
                )
                console.print(
                    f"Image:     {image_finding.image}"
                )
                console.print(
                    f"State:     {image_finding.reason}"
                )

                if image_finding.message:
                    console.print()
                    console.print(
                        "[bold]Kubernetes message[/bold]"
                    )
                    console.print(
                        image_finding.message
                    )

                events = k8s.get_pod_events(
                    pod_name=pod.metadata.name,
                    namespace=namespace,
                )

                relevant_events = [
                    event
                    for event in events
                    if event.reason in {
                        "Failed",
                        "BackOff",
                        "ErrImagePull",
                    }
                ]

                if relevant_events:
                    console.print()
                    console.print(
                        "[bold]Kubernetes events[/bold]"
                    )

                    for event in relevant_events[-5:]:
                        console.print(
                            f"• {event.reason}: "
                            f"{event.message}"
                        )

                console.print()
                console.print("[bold]Diagnosis[/bold]")

                console.print(
                    "Kubernetes cannot pull the configured "
                    "container image."
                )

                console.print()
                console.print(
                    "[bold]Recommended checks[/bold]"
                )

                console.print(
                    "1. Verify the container image name and tag."
                )
                console.print(
                    "2. Confirm the image exists in the registry."
                )
                console.print(
                    "3. Check registry authentication and "
                    "imagePullSecrets."
                )
                console.print(
                    "4. Verify network access to the "
                    "container registry."
                )

                return

            # =====================================================
            # RULE 3 — OOMKILLED
            # =====================================================

            oom_finding = analyze_oom(pod)

            if oom_finding.detected:
                console.print()
                console.print(
                    "[bold red]✗ OOMKilled detected[/bold red]"
                )

                console.print()
                console.print("[bold]Evidence[/bold]")

                console.print(
                    f"Pod:            {pod.metadata.name}"
                )
                console.print(
                    f"Container:      {oom_finding.container}"
                )
                console.print(
                    f"Restarts:       "
                    f"{oom_finding.restart_count}"
                )

                if oom_finding.exit_code is not None:
                    console.print(
                        f"Last exit code: "
                        f"{oom_finding.exit_code}"
                    )

                if oom_finding.memory_limit:
                    console.print(
                        f"Memory limit:   "
                        f"{oom_finding.memory_limit}"
                    )

                console.print()
                console.print("[bold]Diagnosis[/bold]")

                console.print(
                    "The container exceeded its configured memory "
                    "limit and was terminated by the system."
                )

                console.print()
                console.print(
                    "[bold]Recommended checks[/bold]"
                )

                console.print(
                    "1. Review the application's memory usage."
                )
                console.print(
                    "2. Verify the configured memory request "
                    "and limit."
                )
                console.print(
                    "3. Check for memory leaks or unexpected "
                    "memory growth."
                )
                console.print(
                    "4. Increase the memory limit if application "
                    "usage is legitimate."
                )

                return

            # =====================================================
            # RULE 4 — READINESS / LIVENESS PROBE FAILURE
            # =====================================================

            events = k8s.get_pod_events(
                pod_name=pod.metadata.name,
                namespace=namespace,
            )

            probe_finding = analyze_probe_failure(
                pod,
                events,
            )

            if probe_finding.detected:
                console.print()
                console.print(
                    f"[bold red]✗ "
                    f"{probe_finding.probe_type} "
                    f"probe failure detected"
                    f"[/bold red]"
                )

                console.print()
                console.print("[bold]Evidence[/bold]")

                console.print(
                    f"Pod:        {pod.metadata.name}"
                )
                console.print(
                    f"Phase:      {pod.status.phase}"
                )
                console.print(
                    f"Probe type: "
                    f"{probe_finding.probe_type}"
                )

                console.print()
                console.print(
                    "[bold]Kubernetes event[/bold]"
                )

                console.print(
                    probe_finding.message
                )

                console.print()
                console.print("[bold]Diagnosis[/bold]")

                if probe_finding.probe_type == "Readiness":
                    console.print(
                        "The container is running, but Kubernetes "
                        "does not consider it ready to receive "
                        "traffic."
                    )

                else:
                    console.print(
                        "The container is failing its liveness "
                        "check and may be restarted by Kubernetes."
                    )

                console.print()
                console.print(
                    "[bold]Recommended checks[/bold]"
                )

                console.print(
                    "1. Verify the probe path, port, and protocol."
                )
                console.print(
                    "2. Confirm the application is listening on "
                    "the expected port."
                )
                console.print(
                    "3. Review initialDelaySeconds, timeoutSeconds, "
                    "and failureThreshold."
                )
                console.print(
                    "4. Test the health endpoint from inside "
                    "the cluster."
                )

                return

            # =====================================================
            # RULE 5 — CRASHLOOPBACKOFF
            # =====================================================

            crash_finding = analyze_crashloop(pod)

            if crash_finding.detected:
                console.print()
                console.print(
                    "[bold red]"
                    "✗ CrashLoopBackOff detected"
                    "[/bold red]"
                )

                console.print()
                console.print("[bold]Evidence[/bold]")

                console.print(
                    f"Pod:            {pod.metadata.name}"
                )
                console.print(
                    f"Container:      "
                    f"{crash_finding.container}"
                )
                console.print(
                    f"Restarts:       "
                    f"{crash_finding.restart_count}"
                )

                if crash_finding.last_reason:
                    console.print(
                        f"Last reason:    "
                        f"{crash_finding.last_reason}"
                    )

                if crash_finding.exit_code is not None:
                    console.print(
                        f"Last exit code: "
                        f"{crash_finding.exit_code}"
                    )

                # ---------------------------------------------
                # Previous container logs
                # ---------------------------------------------

                logs = k8s.get_previous_logs(
                    pod_name=pod.metadata.name,
                    namespace=namespace,
                    container=crash_finding.container,
                )

                logs = normalize_logs(logs)

                if logs:
                    console.print()
                    console.print(
                        "[bold]"
                        "Previous container logs"
                        "[/bold]"
                    )
                    console.print(
                        logs.strip()
                    )

                console.print()
                console.print("[bold]Diagnosis[/bold]")

                console.print(
                    "The container is repeatedly terminating "
                    "after startup."
                )

                console.print()
                console.print(
                    "[bold]Recommended checks[/bold]"
                )

                console.print(
                    "1. Review the previous container logs."
                )
                console.print(
                    "2. Verify environment variables and "
                    "application configuration."
                )
                console.print(
                    "3. Check referenced Secrets and ConfigMaps."
                )
                console.print(
                    "4. Investigate the application's exit code."
                )

                return

        # =========================================================
        # NO SUPPORTED FAILURE DETECTED
        # =========================================================

        console.print()
        console.print(
            "[green]"
            "✓ No supported failure condition detected."
            "[/green]"
        )

    except typer.Exit:
        raise

    except (ApiException, ConfigException) as exc:
        console.print()
        console.print(
            f"[red]"
            f"✗ Kubernetes connection or diagnostic failed: "
            f"{exc}"
            f"[/red]"
    )

        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()