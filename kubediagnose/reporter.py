import ast

from rich.console import Console


class Reporter:
    """Render KubeDiagnose results to the terminal."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    @staticmethod
    def normalize_logs(logs) -> str | None:
        """Normalize Kubernetes log output."""

        if logs is None:
            return None

        if isinstance(logs, bytes):
            return logs.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(logs, str):
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

    def show_header(
        self,
        workload: str,
        namespace: str,
    ):
        """Display the KubeDiagnose command header."""

        self.console.print()
        self.console.print(
            "[bold cyan]KubeDiagnose[/bold cyan]"
        )
        self.console.print("─" * 50)

        self.console.print(
            f"[bold]Workload:[/bold]  {workload}"
        )
        self.console.print(
            f"[bold]Namespace:[/bold] {namespace}"
        )
        self.console.print()

    def show_connection_success(self):
        """Display successful Kubernetes connection."""

        self.console.print(
            "[green]✓ Connected to Kubernetes API[/green]"
        )

    def show_deployment(
        self,
        deployment,
    ):
        """Display deployment replica information."""

        desired = deployment.spec.replicas or 0
        ready = deployment.status.ready_replicas or 0

        self.console.print(
            f"[bold]Deployment replicas:[/bold] "
            f"{ready}/{desired}"
        )

    def show_pods(self, pods):
        """Display pods belonging to the workload."""

        self.console.print()
        self.console.print("[bold]Pods[/bold]")

        if not pods:
            self.console.print(
                "[yellow]"
                "No pods found for this deployment."
                "[/yellow]"
            )
            return

        for pod in pods:
            self.console.print(
                f"  {pod.metadata.name:<45} "
                f"{pod.status.phase}"
            )

    def show_not_found(
        self,
        workload: str,
        namespace: str,
    ):
        """Display deployment-not-found error."""

        self.console.print(
            f"[red]✗ Deployment '{workload}' was not found "
            f"in namespace '{namespace}'.[/red]"
        )

    def show_no_failure(self):
        """Display healthy/no-supported-failure result."""

        self.console.print()
        self.console.print(
            "[green]"
            "✓ No supported failure condition detected."
            "[/green]"
        )

    def show_kubernetes_error(self, error):
        """Display Kubernetes API/configuration failure."""

        self.console.print()
        self.console.print(
            f"[red]"
            f"✗ Kubernetes connection or diagnostic failed: "
            f"{error}"
            f"[/red]"
        )

    def report(self, result):
        """Render a diagnostic result."""

        reporters = {
            "scheduling": self._report_scheduling,
            "imagepull": self._report_imagepull,
            "oom": self._report_oom,
            "probe": self._report_probe,
            "crashloop": self._report_crashloop,
        }

        reporter = reporters.get(result.kind)

        if reporter is None:
            self.console.print(
                f"[yellow]"
                f"Unsupported diagnostic result: {result.kind}"
                f"[/yellow]"
            )
            return

        reporter(result)

    def _report_scheduling(self, result):
        pod = result.pod
        finding = result.finding

        self.console.print()
        self.console.print(
            "[bold red]✗ FailedScheduling detected[/bold red]"
        )

        self.console.print()
        self.console.print("[bold]Evidence[/bold]")

        self.console.print(
            f"Pod:       {pod.metadata.name}"
        )
        self.console.print(
            f"Phase:     {pod.status.phase}"
        )
        self.console.print(
            "Scheduled: False"
        )
        self.console.print(
            f"Reason:    {finding.reason}"
        )

        if finding.message:
            self.console.print()
            self.console.print(
                "[bold]Scheduler message[/bold]"
            )
            self.console.print(
                finding.message
            )

        events = [
            event
            for event in (result.events or [])
            if event.reason == "FailedScheduling"
        ]

        if events:
            self.console.print()
            self.console.print(
                "[bold]Kubernetes events[/bold]"
            )

            for event in events[-5:]:
                self.console.print(
                    f"• {event.reason}: {event.message}"
                )

        self.console.print()
        self.console.print("[bold]Diagnosis[/bold]")

        self.console.print(
            "Kubernetes cannot find a node that satisfies "
            "the workload's scheduling requirements."
        )

        self.console.print()
        self.console.print(
            "[bold]Recommended checks[/bold]"
        )

        self.console.print(
            "1. Review CPU and memory requests."
        )
        self.console.print(
            "2. Check available node capacity."
        )
        self.console.print(
            "3. Review node selectors and affinity rules."
        )
        self.console.print(
            "4. Check node taints and pod tolerations."
        )

    def _report_imagepull(self, result):
        pod = result.pod
        finding = result.finding

        self.console.print()
        self.console.print(
            f"[bold red]✗ {finding.reason} detected[/bold red]"
        )

        self.console.print()
        self.console.print("[bold]Evidence[/bold]")

        self.console.print(
            f"Pod:       {pod.metadata.name}"
        )
        self.console.print(
            f"Container: {finding.container}"
        )
        self.console.print(
            f"Image:     {finding.image}"
        )
        self.console.print(
            f"State:     {finding.reason}"
        )

        if finding.message:
            self.console.print()
            self.console.print(
                "[bold]Kubernetes message[/bold]"
            )
            self.console.print(
                finding.message
            )

        events = [
            event
            for event in (result.events or [])
            if event.reason
            in {
                "Failed",
                "BackOff",
                "ErrImagePull",
            }
        ]

        if events:
            self.console.print()
            self.console.print(
                "[bold]Kubernetes events[/bold]"
            )

            for event in events[-5:]:
                self.console.print(
                    f"• {event.reason}: {event.message}"
                )

        self.console.print()
        self.console.print("[bold]Diagnosis[/bold]")

        self.console.print(
            "Kubernetes cannot pull the configured "
            "container image."
        )

        self.console.print()
        self.console.print(
            "[bold]Recommended checks[/bold]"
        )

        self.console.print(
            "1. Verify the container image name and tag."
        )
        self.console.print(
            "2. Confirm the image exists in the registry."
        )
        self.console.print(
            "3. Check registry authentication and "
            "imagePullSecrets."
        )
        self.console.print(
            "4. Verify network access to the "
            "container registry."
        )

    def _report_oom(self, result):
        pod = result.pod
        finding = result.finding

        self.console.print()
        self.console.print(
            "[bold red]✗ OOMKilled detected[/bold red]"
        )

        self.console.print()
        self.console.print("[bold]Evidence[/bold]")

        self.console.print(
            f"Pod:            {pod.metadata.name}"
        )
        self.console.print(
            f"Container:      {finding.container}"
        )
        self.console.print(
            f"Restarts:       {finding.restart_count}"
        )

        if finding.exit_code is not None:
            self.console.print(
                f"Last exit code: {finding.exit_code}"
            )

        if finding.memory_limit:
            self.console.print(
                f"Memory limit:   {finding.memory_limit}"
            )

        self.console.print()
        self.console.print("[bold]Diagnosis[/bold]")

        self.console.print(
            "The container exceeded its configured memory "
            "limit and was terminated by the system."
        )

        self.console.print()
        self.console.print(
            "[bold]Recommended checks[/bold]"
        )

        self.console.print(
            "1. Review the application's memory usage."
        )
        self.console.print(
            "2. Verify the configured memory request "
            "and limit."
        )
        self.console.print(
            "3. Check for memory leaks or unexpected "
            "memory growth."
        )
        self.console.print(
            "4. Increase the memory limit if application "
            "usage is legitimate."
        )

    def _report_probe(self, result):
        pod = result.pod
        finding = result.finding

        self.console.print()
        self.console.print(
            f"[bold red]✗ {finding.probe_type} "
            f"probe failure detected[/bold red]"
        )

        self.console.print()
        self.console.print("[bold]Evidence[/bold]")

        self.console.print(
            f"Pod:        {pod.metadata.name}"
        )
        self.console.print(
            f"Phase:      {pod.status.phase}"
        )
        self.console.print(
            f"Probe type: {finding.probe_type}"
        )

        self.console.print()
        self.console.print(
            "[bold]Kubernetes event[/bold]"
        )

        self.console.print(
            finding.message
        )

        self.console.print()
        self.console.print("[bold]Diagnosis[/bold]")

        if finding.probe_type == "Readiness":
            self.console.print(
                "The container is running, but Kubernetes "
                "does not consider it ready to receive traffic."
            )
        else:
            self.console.print(
                "The container is failing its liveness check "
                "and may be restarted by Kubernetes."
            )

        self.console.print()
        self.console.print(
            "[bold]Recommended checks[/bold]"
        )

        self.console.print(
            "1. Verify the probe path, port, and protocol."
        )
        self.console.print(
            "2. Confirm the application is listening on "
            "the expected port."
        )
        self.console.print(
            "3. Review initialDelaySeconds, timeoutSeconds, "
            "and failureThreshold."
        )
        self.console.print(
            "4. Test the health endpoint from inside "
            "the cluster."
        )

    def _report_crashloop(self, result):
        pod = result.pod
        finding = result.finding

        self.console.print()
        self.console.print(
            "[bold red]✗ CrashLoopBackOff detected[/bold red]"
        )

        self.console.print()
        self.console.print("[bold]Evidence[/bold]")

        self.console.print(
            f"Pod:            {pod.metadata.name}"
        )
        self.console.print(
            f"Container:      {finding.container}"
        )
        self.console.print(
            f"Restarts:       {finding.restart_count}"
        )

        if finding.last_reason:
            self.console.print(
                f"Last reason:    {finding.last_reason}"
            )

        if finding.exit_code is not None:
            self.console.print(
                f"Last exit code: {finding.exit_code}"
            )

        logs = self.normalize_logs(
            result.logs
        )

        if logs:
            self.console.print()
            self.console.print(
                "[bold]Previous container logs[/bold]"
            )
            self.console.print(
                logs.strip()
            )

        self.console.print()
        self.console.print("[bold]Diagnosis[/bold]")

        self.console.print(
            "The container is repeatedly terminating "
            "after startup."
        )

        self.console.print()
        self.console.print(
            "[bold]Recommended checks[/bold]"
        )

        self.console.print(
            "1. Review the previous container logs."
        )
        self.console.print(
            "2. Verify environment variables and "
            "application configuration."
        )
        self.console.print(
            "3. Check referenced Secrets and ConfigMaps."
        )
        self.console.print(
            "4. Investigate the application's exit code."
        )