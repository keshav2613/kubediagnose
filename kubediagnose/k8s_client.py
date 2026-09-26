from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException


class KubernetesClient:
    """Wrapper around the Kubernetes Python client."""

    def __init__(self):
        """
        Load the user's kubeconfig and initialize
        the Kubernetes API clients.
        """

        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()

        self.apps_api = client.AppsV1Api()
        self.core_api = client.CoreV1Api()

    def get_deployment(
        self,
        name: str,
        namespace: str,
    ):
        """
        Return a Kubernetes deployment.

        Returns None when the deployment does not exist.
        """

        try:
            return self.apps_api.read_namespaced_deployment(
                name=name,
                namespace=namespace,
            )

        except ApiException as exc:
            if exc.status == 404:
                return None

            raise

    def get_deployment_pods(
        self,
        deployment,
        namespace: str,
    ):
        """
        Return pods belonging to a deployment.
        """

        labels = deployment.spec.selector.match_labels or {}

        label_selector = ",".join(
            f"{key}={value}"
            for key, value in labels.items()
        )

        return self.core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
        ).items

    def get_previous_logs(
        self,
        pod_name: str,
        namespace: str,
        container: str,
    ) -> str | None:
        """
        Return logs from the previous instance of a restarted container.

        Useful when diagnosing CrashLoopBackOff.
        """

        try:
            logs = self.core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                previous=True,
                tail_lines=20,
            )

            if isinstance(logs, bytes):
                logs = logs.decode(
                    "utf-8",
                    errors="replace",
                )

            return logs

        except ApiException:
            return None

    def get_pod_events(
        self,
        pod_name: str,
        namespace: str,
    ):
        """
        Return Kubernetes events associated with a pod.

        Events provide additional evidence for failures such as
        ImagePullBackOff and FailedScheduling.
        """

        field_selector = (
            f"involvedObject.name={pod_name},"
            "involvedObject.kind=Pod"
        )

        try:
            events = self.core_api.list_namespaced_event(
                namespace=namespace,
                field_selector=field_selector,
            )

            return events.items

        except ApiException:
            return []