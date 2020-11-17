"""
High-level interface to the Kubernetes APIs used to retreive logs from
active pods.
"""
from typing import cast, Optional

from kubernetes import client as k8s


def get_latest_pod_name(namespace: str, pod_name_prefix: str) -> Optional[str]:
    """Get full name of most recently started pod with a name prefix.

    :param namespace: The namespace in which to look for pods.
    :param pod_name_prefix: The pod name prefix to filter pods by.
    :return: The full name of a pod.
    """
    pod_list = k8s.CoreV1Api().list_namespaced_pod(namespace=namespace)
    if pod_list:
        filtered_pod_objects = sorted(
            [pod_object
                for pod_object in pod_list.items
                if pod_object.metadata.name.startswith(pod_name_prefix)],
            key=lambda pod_object: pod_object.status.start_time,
            reverse=True
        )
        if filtered_pod_objects:
            return cast(str, filtered_pod_objects[0].metadata.name)
    return None


def get_pod_logs(namespace: str, pod_name: str) -> str:
    """Retreive the logs from the named pod.

    :param namespace: The namespace in which to look for the pods.
    :param pod_name: The name of the pod to retreive logs from.
    :return: The pod logs as a single string object.
    """
    pod_logs = k8s.CoreV1Api().read_namespaced_pod_log(
        namespace=namespace,
        name=pod_name
    )
    return cast(str, pod_logs)
