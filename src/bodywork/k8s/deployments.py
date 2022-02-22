# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020-2022  Bodywork Machine Learning Ltd.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
High-level interface to the Kubernetes APIs as used to create and manage
Bodywork service deployment stages.
"""
from datetime import datetime
from enum import Enum
from time import sleep, time
from typing import Dict, Iterable, List, Any

from kubernetes import client as k8s

from ..constants import BODYWORK_DOCKER_IMAGE, BODYWORK_STAGES_SERVICE_ACCOUNT
from .utils import make_valid_k8s_name


class DeploymentStatus(Enum):
    """Possible states of a k8s deployment."""

    COMPLETE = "complete"
    PROGRESSING = "progressing"


def configure_service_stage_deployment(
    namespace: str,
    stage_name: str,
    project_name: str,
    project_repo_url: str,
    git_commit_hash: str,
    project_repo_branch: str = None,
    image: str = BODYWORK_DOCKER_IMAGE,
    replicas: int = 1,
    port: int = 80,
    container_env_vars: List[k8s.V1EnvVar] = None,
    cpu_request: float = None,
    memory_request: int = None,
    seconds_to_be_ready_before_completing: int = 30,
) -> k8s.V1Deployment:
    """Configure a Bodywork service stage k8s deployment.

    :param namespace: The k8s namespace to target deployment.
    :param stage_name: The name of the Bodywork project stage that
        will need to be executed.
    :param project_name: The name of the Bodywork project that the stage
        belongs to.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param git_commit_hash: The git commit hash of this Bodywork project.
    :param project_repo_branch: The Bodywork project Git repository
        branch to use, defaults to None.
    :param image: Docker image to use for running the stage within,
        defaults to BODYWORK_DOCKER_IMAGE.
    :param replicas: Number of containers to create as part of this
        deployment, defaults to 1.
    :param port: The port to open when exposing the service, defaults
        to 80.
    :param container_env_vars: Optional list of environment variables
        (e.g. secrets) to set in the container, defaults to None.
    :param cpu_request: CPU resource to request from a node, expressed
        as a decimal number, defaults to None.
    :param memory_request: Memory resource to request from a node, expressed
        as an integer number of megabytes, defaults to None.
    :param seconds_to_be_ready_before_completing: Time (in seconds) that
        the deployment must be observed as being 'ready', before its
        status is moved to complete. Defaults to 30s.
    :return: A configured k8s deployment object.

    """
    service_name = make_valid_k8s_name(stage_name)
    container_args = (
        [project_repo_url, stage_name, f"--branch={project_repo_branch}"]
        if project_repo_branch
        else [project_repo_url, stage_name]
    )
    container_resources = k8s.V1ResourceRequirements(
        requests={
            "cpu": f"{cpu_request}" if cpu_request else None,
            "memory": f"{memory_request}M" if memory_request else None,
        }
    )
    container = k8s.V1Container(
        name="bodywork",
        image=image,
        image_pull_policy="Always",
        resources=container_resources,
        env=container_env_vars,
        command=["bodywork", "stage"],
        args=container_args,
    )
    pod_spec = k8s.V1PodSpec(
        service_account_name=BODYWORK_STAGES_SERVICE_ACCOUNT,
        containers=[container],
        restart_policy="Always",
    )
    pod_template_spec = k8s.V1PodTemplateSpec(
        metadata=k8s.V1ObjectMeta(
            labels={
                "app": "bodywork",
                "stage": service_name,
                "deployment-name": project_name,
                "git-commit-hash": git_commit_hash,
            },
            annotations={"last-updated": datetime.now().isoformat()},
        ),
        spec=pod_spec,
    )
    deployment_spec = k8s.V1DeploymentSpec(
        replicas=replicas,
        template=pod_template_spec,
        selector={"matchLabels": {"stage": service_name}},
        revision_history_limit=0,
        min_ready_seconds=seconds_to_be_ready_before_completing,
    )
    deployment_metadata = k8s.V1ObjectMeta(
        namespace=namespace,
        name=service_name,
        annotations={"port": str(port)},
        labels={
            "app": "bodywork",
            "stage": service_name,
            "deployment-name": project_name,
            "git-commit-hash": git_commit_hash,
        },
    )
    deployment = k8s.V1Deployment(metadata=deployment_metadata, spec=deployment_spec)
    return deployment


def create_deployment(deployment: k8s.V1Deployment) -> None:
    """Create a deployment on a k8s cluster.

    :param deployment: A configured deployment object.
    """
    k8s.AppsV1Api().create_namespaced_deployment(
        body=deployment, namespace=deployment.metadata.namespace
    )


def is_existing_deployment(namespace: str, name: str) -> bool:
    """Determine if the deployment already exists within the namespace.

    :param namespace: Namespace in which to look for deployment.
    :param name: Name of deployment in namespace.
    :return: Boolean flag for the deployment within the namespace.
    """
    existing_deployments = k8s.AppsV1Api().list_namespaced_deployment(
        namespace=namespace
    )
    existing_deployment_names = [
        deployment.metadata.name for deployment in existing_deployments.items
    ]
    return True if name in existing_deployment_names else False


def update_deployment(deployment: k8s.V1Deployment) -> None:
    """Update a deployment on a k8s cluster.

    :param deployment: A configured deployment object.
    """
    k8s.AppsV1Api().patch_namespaced_deployment(
        body=deployment,
        name=deployment.metadata.name,
        namespace=deployment.metadata.namespace,
    )


def rollback_deployment(deployment: k8s.V1Deployment) -> None:
    """Rollback a deployment to its previous version.

    The Kubernetes API has no dedicated endpoint for managing rollbacks.
    This function was implemented by reverse-engineering the API calls
    made by the equivalent kubectl command,`kubectl rollout undo ...`.

    :param deployment: A configured deployment object.
    """
    name = deployment.metadata.name
    namespace = deployment.metadata.namespace

    associated_replica_sets = k8s.AppsV1Api().list_namespaced_replica_set(
        namespace=namespace,
        label_selector=(f'app=bodywork,stage={deployment.metadata.labels["stage"]}'),
    )

    revision_ordered_replica_sets = sorted(
        associated_replica_sets.items,
        key=lambda e: str(e.metadata.annotations["deployment.kubernetes.io/revision"]),
        reverse=True,
    )

    rollback_replica_set = (
        revision_ordered_replica_sets[0]
        if len(revision_ordered_replica_sets) == 1
        else revision_ordered_replica_sets[1]
    )

    rollback_revision_number = rollback_replica_set.metadata.annotations[
        "deployment.kubernetes.io/revision"
    ]

    is_new_deployment = (
        rollback_revision_number == "1" and len(revision_ordered_replica_sets) == 1
    )

    if is_new_deployment:
        delete_deployment(namespace, name)
    else:
        patch = [
            {
                "op": "replace",
                "path": "/spec/template",
                "value": rollback_replica_set.spec.template,
            },
            {
                "op": "replace",
                "path": "/metadata/annotations",
                "value": {
                    "deployment.kubernetes.io/revision": rollback_revision_number,
                    **deployment.metadata.annotations,
                },
            },
        ]
        k8s.AppsV1Api().patch_namespaced_deployment(
            body=patch, name=name, namespace=namespace
        )


def delete_all_namespace_deployments(namespace: str) -> None:
    """Delete all deployments within a k8s namespace.

    :param namespace: Namespace in which to look for deployments.
    """
    existing_deployments = k8s.AppsV1Api().list_namespaced_deployment(
        namespace=namespace
    )
    existing_deployment_names = [
        deployment.metadata.name for deployment in existing_deployments.items
    ]
    for name in existing_deployment_names:
        delete_deployment(namespace, name)


def delete_deployment(namespace: str, name: str) -> None:
    """Delete a deployment on a k8s cluster.

    :param namespace: Namespace in which to look for deployment.
    :param name: Name of deployment in namespace.
    """
    k8s.AppsV1Api().delete_namespaced_deployment(
        name=name,
        namespace=namespace,
        body=k8s.V1DeleteOptions(propagation_policy="Background"),
    )


def _get_deployment_status(deployment: k8s.V1Deployment) -> DeploymentStatus:
    """Get the latest status of a deployment created on a k8s cluster.

    :param deployment: A configured job object.
    :raises RuntimeError: If the deployment cannot be found or the status
        cannot be identified.
    :return: The current status of the deployment.
    """
    name = deployment.metadata.name
    namespace = deployment.metadata.namespace
    try:
        k8s_deployment_query = k8s.AppsV1Api().list_namespaced_deployment(
            namespace=namespace
        )
        k8s_deployment_data = [
            deployment
            for deployment in k8s_deployment_query.items
            if deployment.metadata.name == name
        ][0]
    except IndexError as e:
        msg = (
            f"cannot find deployment={deployment.metadata.name} in "
            f"namespace={deployment.metadata.namespace}"
        )
        raise RuntimeError(msg) from e

    if (
        k8s_deployment_data.status.available_replicas is not None
        and k8s_deployment_data.status.unavailable_replicas is None
    ):
        return DeploymentStatus.COMPLETE
    elif (
        k8s_deployment_data.status.available_replicas is None
        or k8s_deployment_data.status.unavailable_replicas > 0
    ):
        return DeploymentStatus.PROGRESSING
    else:
        msg = (
            f"cannot determine status for deployment={name} in "
            f"namespace={namespace}"
        )
        raise RuntimeError(msg)


def monitor_deployments_to_completion(
    deployments: Iterable[k8s.V1Deployment],
    timeout_seconds: int = 10,
    polling_freq_seconds: int = 1,
    wait_before_start_seconds: int = 5,
) -> bool:
    """Monitor deployment status until completion or timeout.

    :param deployments: The deployments to monitor.
    :param timeout_seconds: How long to keep monitoring status before
        calling a timeout, defaults to 10.
    :param polling_freq_seconds: Time (in seconds) between status
        polling, defaults to 1.
    :param wait_before_start_seconds: Time to wait before starting to
        monitor deployments - e.g. to allow deployments to be created.
    :raises TimeoutError: If the timeout limit is reached and the deployments
        are still marked as progressing.
    :return: True if all of the deployments are successful.
    """
    sleep(wait_before_start_seconds)
    start_time = time()
    deployments_status = [
        _get_deployment_status(deployment) for deployment in deployments
    ]
    while any(status is DeploymentStatus.PROGRESSING for status in deployments_status):
        sleep(polling_freq_seconds)
        if time() - start_time >= timeout_seconds:
            unsuccessful_deployments_msg = [
                (
                    f"deployment={deployment.metadata.name} in "
                    f"namespace={deployment.metadata.namespace}"
                )
                for deployment, status in zip(deployments, deployments_status)
                if status != DeploymentStatus.COMPLETE
            ]
            msg = (
                f'{"; ".join(unsuccessful_deployments_msg)} have yet to reach '
                f"status=complete after {timeout_seconds}s"
            )
            raise TimeoutError(msg)
        deployments_status = [
            _get_deployment_status(deployment) for deployment in deployments
        ]
    return True


def deployment_id(deployment_name: str, stage_name: str) -> str:
    """Return deployment ID implied by deployment and stage names.

    Args:
        deployment_name: The name given to the Bodywork deployment
            project.
        stage_name: The name of the stage that deployed a single
            service, within the Bodywork deployment project.

    Returns:
        Deployment ID string to use for locating services.
    """
    return f"{deployment_name}/{stage_name}"


def list_service_stage_deployments(
    namespace: str = None,
    name: str = None,
) -> Dict[str, Dict[str, Any]]:
    """Get all service deployments and their high-level info.

    :param namespace: Namespace in which to list services.
    :param name: Name of service.
    :return: Dict of deployments and their attributes.
    """
    label_selector = f"app=bodywork,deployment-name={name}" if name else "app=bodywork"
    if namespace:
        k8s_deployment_query = k8s.AppsV1Api().list_namespaced_deployment(
            namespace=namespace, label_selector=label_selector
        )
    else:
        k8s_deployment_query = k8s.AppsV1Api().list_deployment_for_all_namespaces(
            label_selector=label_selector
        )
    deployment_info = {}
    for deployment in k8s_deployment_query.items:
        exposed_as_cluster_service = is_exposed_as_cluster_service(
            deployment.metadata.namespace, deployment.metadata.name
        )
        id = deployment_id(
            deployment.metadata.labels["deployment-name"],
            deployment.metadata.labels["stage"],
        )
        deployment_info[id] = {
            "name": deployment.metadata.name,
            "namespace": deployment.metadata.namespace,
            "service_exposed": exposed_as_cluster_service,
            "service_url": (
                cluster_service_url(
                    deployment.metadata.namespace, deployment.metadata.name
                )
                if exposed_as_cluster_service
                else "none"
            ),
            "service_port": (
                deployment.metadata.annotations["port"]
                if exposed_as_cluster_service
                else "none"
            ),
            "available_replicas": (
                0
                if deployment.status.available_replicas is None
                else deployment.status.available_replicas
            ),
            "unavailable_replicas": (
                0
                if deployment.status.unavailable_replicas is None
                else deployment.status.unavailable_replicas
            ),
            "git_url": deployment.spec.template.spec.containers[0].args[0],
            "git_branch": deployment.spec.template.spec.containers[0].args[1],
            "git_commit_hash": deployment.metadata.labels.get("git-commit-hash", "NA"),
            "has_ingress": (
                has_ingress(deployment.metadata.namespace, deployment.metadata.name)
            ),
            "ingress_route": (
                ingress_route(deployment.metadata.namespace, deployment.metadata.name)
                if has_ingress(deployment.metadata.namespace, deployment.metadata.name)
                else "none"
            ),
        }

    return deployment_info


def cluster_service_url(namespace: str, deployment_name: str) -> str:
    """Standardised URL to a service deployment.

    :param namespace: Namespace in which the deployment exists.
    :param deployment_name: The deployment's name.
    :return: The internal URL to access the cluster service from within
        the cluster.
    """
    return f"http://{deployment_name}.{namespace}.svc.cluster.local"


def expose_deployment_as_cluster_service(deployment: k8s.V1Deployment) -> None:
    """Expose a deployment as a Kubernetes service.

    :param deployment: A configured deployment object.
    """
    namespace = deployment.metadata.namespace
    name = deployment.metadata.name
    pod_label_selector = deployment.spec.selector["matchLabels"]
    pod_port = int(deployment.metadata.annotations["port"])

    service_spec = k8s.V1ServiceSpec(
        type="ClusterIP",
        selector=pod_label_selector,
        ports=[k8s.V1ServicePort(port=pod_port, target_port=pod_port)],
    )
    service_metadata = k8s.V1ObjectMeta(
        namespace=namespace, name=name, labels={"app": "bodywork", "stage": name}
    )
    service = k8s.V1Service(metadata=service_metadata, spec=service_spec)
    k8s.CoreV1Api().create_namespaced_service(namespace=namespace, body=service)


def is_exposed_as_cluster_service(namespace: str, name: str) -> bool:
    """Is a deployment exposed as a cluster service.

    :param namespace: Namespace in which to look for services.
    :param name: The name of the service.
    """
    services = k8s.CoreV1Api().list_namespaced_service(namespace=namespace)
    service_names = [service.metadata.name for service in services.items]
    return True if name in service_names else False


def stop_exposing_cluster_service(namespace: str, name: str) -> None:
    """Delete a service associated with a deployment.

    :param namespace: Namespace in which exists the service to delete.
    :param name: The name of the service.
    """
    k8s.CoreV1Api().delete_namespaced_service(
        namespace=namespace, name=name, propagation_policy="Background"
    )


def ingress_route(namespace: str, deployment_name: str) -> str:
    """Standardised route to a service deployment.

    :param namespace: Namespace in which the deployment exists.
    :param deployment_name: The deployment's name.
    :return: A route to use for ingress to the service deployment.
    """
    return f"/{namespace}/{deployment_name}"


def create_deployment_ingress(deployment: k8s.V1Deployment) -> None:
    """Create an ingress to a service backed by a deployment.

    :param deployment: A configured deployment object.
    """
    namespace = deployment.metadata.namespace
    name = deployment.metadata.name
    pod_port = int(deployment.metadata.annotations["port"])

    ingress_path = f"{ingress_route(namespace, name)}(/|$)(.*)"

    ingress_spec = k8s.V1IngressSpec(
        rules=[
            k8s.V1IngressRule(
                http=k8s.V1HTTPIngressRuleValue(
                    paths=[
                        k8s.V1HTTPIngressPath(
                            path=ingress_path,
                            path_type="Exact",
                            backend=k8s.V1IngressBackend(
                                service=k8s.V1IngressServiceBackend(
                                    name=name,
                                    port=k8s.V1ServiceBackendPort(number=pod_port),
                                )
                            ),
                        )
                    ]
                )
            )
        ]
    )

    ingress_metadata = k8s.V1ObjectMeta(
        namespace=namespace,
        name=name,
        annotations={
            "kubernetes.io/ingress.class": "nginx",
            "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
        },
        labels={"app": "bodywork", "stage": name},
    )

    ingress = k8s.V1Ingress(metadata=ingress_metadata, spec=ingress_spec)

    k8s.NetworkingV1Api().create_namespaced_ingress(namespace=namespace, body=ingress)


def delete_deployment_ingress(namespace: str, name: str) -> None:
    """Delete an ingress to a service backed by a deployment.

    :param namespace: Namespace in which exists the ingress to delete.
    :param name: The name of the ingress.
    """
    k8s.NetworkingV1Api().delete_namespaced_ingress(
        namespace=namespace, name=name, propagation_policy="Background"
    )


def has_ingress(namespace: str, name: str) -> bool:
    """Does a service backed by a deployment have an ingress?

    :param namespace: Namespace in which to look for ingress resources.
    :param name: The name of the ingress.
    """
    ingresses = k8s.NetworkingV1Api().list_namespaced_ingress(
        namespace=namespace, label_selector="app=bodywork"
    )
    ingress_names = [ingress.metadata.name for ingress in ingresses.items]
    return True if name in ingress_names else False
