# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020-2021  Bodywork Machine Learning Ltd.

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
from typing import Dict, Iterable, List, Optional

from kubernetes import client as k8s

from ..constants import (
    BODYWORK_DOCKER_IMAGE,
    BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT,
    SSH_GITHUB_KEY_ENV_VAR,
    SSH_GITHUB_SECRET_NAME
)


class DeploymentStatus(Enum):
    "Possible states of a k8s deployment."

    COMPLETE = 'complete'
    PROGRESSING = 'progressing'


def configure_service_stage_deployment(
    namespace: str,
    stage_name: str,
    project_name: str,
    project_repo_url: str,
    project_repo_branch: str = 'master',
    image: str = BODYWORK_DOCKER_IMAGE,
    replicas: int = 1,
    port: int = 80,
    container_env_vars: Optional[List[k8s.V1EnvVar]] = None,
    cpu_request: Optional[float] = None,
    memory_request: Optional[int] = None,
    seconds_to_be_ready_before_completing: int = 30
) -> k8s.V1Deployment:
    """Configure a Bodywork service stage k8s deployment.

    :param namespace: The k8s namespace to target deployment.
    :param stage_name: The name of the Bodywork project stage that
        will need to be executed.
    :param project_name: The name of the Bodywork project that the stage
        belongs to.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The Bodywork project Git repository
        branch to use, defaults to 'master'.
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
    vcs_env_vars = [
        k8s.V1EnvVar(
            name=SSH_GITHUB_KEY_ENV_VAR,
            value_from=k8s.V1EnvVarSource(
                secret_key_ref=k8s.V1SecretKeySelector(
                    key=SSH_GITHUB_KEY_ENV_VAR,
                    name=SSH_GITHUB_SECRET_NAME,
                    optional=True
                )
            )
        )
    ]
    env_vars = vcs_env_vars + container_env_vars if container_env_vars else vcs_env_vars
    container_resources = k8s.V1ResourceRequirements(
        requests={
            'cpu': f'{cpu_request}' if cpu_request else None,
            'memory': f'{memory_request}M' if memory_request else None
        }
    )
    container = k8s.V1Container(
        name='bodywork',
        image=image,
        image_pull_policy='Always',
        resources=container_resources,
        env=env_vars,
        command=['bodywork', 'stage'],
        args=[project_repo_url, project_repo_branch, stage_name]
    )
    pod_spec = k8s.V1PodSpec(
        service_account_name=BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT,
        containers=[container],
        restart_policy='Always'
    )
    pod_template_spec = k8s.V1PodTemplateSpec(
        metadata=k8s.V1ObjectMeta(
            labels={'app': stage_name},
            annotations={'last-updated': datetime.now().isoformat()}
        ),
        spec=pod_spec
    )
    deployment_spec = k8s.V1DeploymentSpec(
        replicas=replicas,
        template=pod_template_spec,
        selector={'matchLabels': {'app': stage_name}},
        revision_history_limit=0,
        min_ready_seconds=seconds_to_be_ready_before_completing
    )
    deployment_metadata = k8s.V1ObjectMeta(
        namespace=namespace,
        name=f'{project_name}--{stage_name}',
        annotations={'port': str(port)}
    )
    deployment = k8s.V1Deployment(
        metadata=deployment_metadata,
        spec=deployment_spec
    )
    return deployment


def create_deployment(deployment: k8s.V1Deployment) -> None:
    """Create a deployment on a k8s cluster.

    :param deployment: A configured deployment object.
    """
    k8s.AppsV1Api().create_namespaced_deployment(
        body=deployment,
        namespace=deployment.metadata.namespace
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
        namespace=deployment.metadata.namespace
    )


def rollback_deployment(deployment: k8s.V1Deployment) -> None:
    """Rollback a deployment to its previous version.

    The Kubernetes API has no dedicated enpoint for managing rollbacks.
    This function was implemented by reverse-engineering the API calls
    made by the equivalent kubectl command,`kubectl rollout undo ...`.

    :param deployment: A configured deployment object.
    """
    name = deployment.metadata.name
    namespace = deployment.metadata.namespace

    associated_replica_sets = k8s.AppsV1Api().list_namespaced_replica_set(
        namespace=namespace,
        label_selector=f'app={deployment.spec.template.metadata.labels["app"]}'
    )

    revision_ordered_replica_sets = sorted(
        associated_replica_sets.items,
        key=lambda e: e.metadata.annotations['deployment.kubernetes.io/revision'],
        reverse=True
    )

    rollback_replica_set = (
        revision_ordered_replica_sets[0]
        if len(revision_ordered_replica_sets) == 1
        else revision_ordered_replica_sets[1]
    )

    rollback_revision_number = (
        rollback_replica_set
        .metadata
        .annotations['deployment.kubernetes.io/revision']
    )

    patch = [
        {
            'op': 'replace',
            'path': '/spec/template',
            'value': rollback_replica_set.spec.template
        },
        {
            'op': 'replace',
            'path': '/metadata/annotations',
            'value': {
                'deployment.kubernetes.io/revision': rollback_revision_number,
                **deployment.metadata.annotations
            }
        }
    ]

    k8s.AppsV1Api().patch_namespaced_deployment(
        body=patch,
        name=name,
        namespace=namespace
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
        body=k8s.V1DeleteOptions(propagation_policy='Background')
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
        msg = (f'cannot find deployment={deployment.metadata.name} in '
               f'namespace={deployment.metadata.namespace}')
        raise RuntimeError(msg) from e

    if (k8s_deployment_data.status.available_replicas is not None
            and k8s_deployment_data.status.unavailable_replicas is None):
        return DeploymentStatus.COMPLETE
    elif (k8s_deployment_data.status.available_replicas is None
            or k8s_deployment_data.status.unavailable_replicas > 0):
        return DeploymentStatus.PROGRESSING
    else:
        msg = (f'cannot determine status for deployment={name} in '
               f'namespace={namespace}')
        raise RuntimeError(msg)


def monitor_deployments_to_completion(
    deployments: Iterable[k8s.V1Deployment],
    timeout_seconds: int = 10,
    polling_freq_seconds: int = 1,
    wait_before_start_seconds: int = 5
) -> bool:
    """Monitor deployment status until completion or timeout.

    :param deployents: The deployments to monitor.
    :param timeout_seconds: How long to keep monitoring status before
        calling a timeout, defaults to 10.
    :param polling_freq_seconds: Time (in seconds) between status
        polling, defaults to 1.
    :param wait_before_start_seconds: Time to wait before starting to
        monitor deployments - e.g. to allow deployments to be created.
    :raises TimeoutError: If the timeout limit is reached and the deployments
        are still marked as progressing.
    :return: True if all of the deployments are successfull.
    """
    sleep(wait_before_start_seconds)
    start_time = time()
    deployments_status = [
        _get_deployment_status(deployment)
        for deployment in deployments
    ]
    while any(status is DeploymentStatus.PROGRESSING for status in deployments_status):
        sleep(polling_freq_seconds)
        if time() - start_time >= timeout_seconds:
            unsuccessful_deployments_msg = [
                (f'deployment={deployment.metadata.name} in '
                 f'namespace={deployment.metadata.namespace}')
                for deployment, status in zip(deployments, deployments_status)
                if status != DeploymentStatus.COMPLETE
            ]
            msg = (f'{"; ".join(unsuccessful_deployments_msg)} have yet to reach '
                   f'status=complete after {timeout_seconds}s')
            raise TimeoutError(msg)
        deployments_status = [
            _get_deployment_status(deployment)
            for deployment in deployments
        ]
    return True


def list_service_stage_deployments(namespace: str) -> Dict[str, Dict[str, str]]:
    """Get all service deployments and their high-level info.

    :param namespace: Namespace in which to list cronjobs.
    """
    k8s_deployment_query = k8s.AppsV1Api().list_namespaced_deployment(
        namespace=namespace
    )
    deployment_info = {
        deployment.metadata.name: {
            'service_url': (
                f'http://{deployment.metadata.name}:'
                f'{deployment.metadata.annotations["port"]}'
            ),
            'service_exposed': (
                'true'
                if is_exposed_as_cluster_service(
                    deployment.metadata.namespace,
                    deployment.metadata.name
                )
                else 'false'
            ),
            'available_replicas': (
                0
                if deployment.status.available_replicas is None
                else deployment.status.available_replicas),
            'unavailable_replicas': (
                0
                if deployment.status.unavailable_replicas is None
                else deployment.status.unavailable_replicas),
            'git_url': deployment.spec.template.spec.containers[0].args[0],
            'git_branch': deployment.spec.template.spec.containers[0].args[1]
        }
        for deployment in k8s_deployment_query.items
    }
    return deployment_info


def expose_deployment_as_cluster_service(deployment: k8s.V1Deployment) -> None:
    """Expose a deployment as a Kubernetes service.

    :param deployment: A configured deployment object.
    """
    namespace = deployment.metadata.namespace
    name = deployment.metadata.name
    pod_label_selector = deployment.spec.selector['matchLabels']
    pod_port = int(deployment.metadata.annotations['port'])

    service_spec = k8s.V1ServiceSpec(
        type='ClusterIP',
        selector=pod_label_selector,
        ports=[k8s.V1ServicePort(port=pod_port, target_port=pod_port)]
    )
    service_metadata = k8s.V1ObjectMeta(
        namespace=namespace,
        name=name
    )
    service = k8s.V1Service(
        metadata=service_metadata,
        spec=service_spec
    )
    k8s.CoreV1Api().create_namespaced_service(
        namespace=namespace,
        body=service
    )


def is_exposed_as_cluster_service(namespace: str, name: str) -> bool:
    """Is a deployment exposed as a cluster service.

    :param namespace: Namespace in which to look for services.
    :param names: The name of the service.
    """
    services = k8s.CoreV1Api().list_namespaced_service(
        namespace=namespace
    )
    service_names = [service.metadata.name for service in services.items]
    return True if name in service_names else False


def stop_exposing_cluster_service(namespace: str, name: str) -> None:
    """Delete a service associated with a deployment.

    :param namespace: Namespace in which exists the service to delete.
    :param names: The name of the service.
    """
    k8s.CoreV1Api().delete_namespaced_service(
        namespace=namespace,
        name=name,
        propagation_policy='Background'
    )
