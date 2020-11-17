"""
High-level interface to the Kubernetes core API as used to manage
Kubernetes namespaces for Bodywork projects.
"""
from kubernetes import client as k8s


def namespace_exists(namespace: str) -> bool:
    """Does the namespace exist on the Kubernetes cluster.

    :param namespace: Kubernetes namespace to check.
    :return: True if the namespace was found, othewise False.
    """
    namespace_objects = (
        k8s.CoreV1Api()
        .list_namespace()
        .items
    )
    namespace_names = [
        namespace_object.metadata.name
        for namespace_object in namespace_objects
    ]
    return True if namespace in namespace_names else False


def create_namespace(name: str) -> None:
    """Create a new namespace.

    :param namespace: Kubernetes namespace to create.
    """
    k8s.CoreV1Api().create_namespace(
        body=k8s.V1Namespace(
            metadata=k8s.V1ObjectMeta(name=name)
        )
    )


def delete_namespace(name: str) -> None:
    """Delete a new namespace.

    :param namespace: Kubernetes namespace to delete.
    """
    k8s.CoreV1Api().delete_namespace(
        name=name,
        propagation_policy='Background'
    )
