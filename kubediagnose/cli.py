import typer
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from rich.console import Console
from rich.panel import Panel

from kubediagnose.engine import DiagnosticEngine
from kubediagnose.k8s_client import KubernetesClient
from kubediagnose.reporter import Reporter

app = typer.Typer(
    help="Evidence-based Kubernetes workload diagnostics."
)

console = Console()
reporter = Reporter(console)


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

    reporter.show_header(
        workload=workload,
        namespace=namespace,
    )

    try:
        # ---------------------------------------------------------
        # Kubernetes API
        # ---------------------------------------------------------

        k8s = KubernetesClient()

        # ---------------------------------------------------------
        # Deployment discovery
        # ---------------------------------------------------------

        deployment = k8s.get_deployment(
            name=workload,
            namespace=namespace,
        )

        if deployment is None:
            reporter.show_not_found(
                workload=workload,
                namespace=namespace,
            )

            raise typer.Exit(code=1)

        # ---------------------------------------------------------
        # Pod discovery
        # ---------------------------------------------------------

        pods = k8s.get_deployment_pods(
            deployment=deployment,
            namespace=namespace,
        )

        reporter.show_connection_success()
        reporter.show_deployment(deployment)
        reporter.show_pods(pods)

        if not pods:
            return

        # ---------------------------------------------------------
        # Diagnostic engine
        # ---------------------------------------------------------

        engine = DiagnosticEngine(k8s)

        result = engine.diagnose_pods(
            pods=pods,
            namespace=namespace,
        )

        # ---------------------------------------------------------
        # Report
        # ---------------------------------------------------------

        if result is None:
            reporter.show_no_failure()
            return

        reporter.report(result)

    except typer.Exit:
        raise

    except (ApiException, ConfigException) as exc:
        reporter.show_kubernetes_error(exc)

        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()