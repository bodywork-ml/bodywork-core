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
Helper functions for working with the Kubernetes API.
"""
import json
import re
from typing import cast, Iterable, List, Tuple, Union

from kubernetes.client.rest import ApiException
from kubernetes import client as k8s

from ..exceptions import BodyworkClusterResourcesError

EnvVars = k8s.V1EnvVar


def api_exception_msg(e: ApiException) -> str:
    """Get k8s API error message from exception object.

    :param e: Kubernetes API exception
    :return: Error message returned by the k8s API.
    """
    try:
        body = json.loads(e.body)
        message = body["message"]
        return cast(str, message)
    except (KeyError, TypeError):
        return ""


def make_valid_k8s_name(name: str) -> str:
    """Remove invalid characters from k8s resource name.

    :param name: Original intended name.
    :return: Valid Kubernetes resource name.
    """
    return re.sub(r"[^a-zA-Z0-9.]+", "-", name.strip())


def create_k8s_environment_variables(
    key_value_pairs: List[Tuple[str, str]]
) -> List[k8s.V1EnvVar]:
    """Creates K8s environment variable from key/value pairs.

    :param key_value_pairs: Environment variables to create.
    :return: List of K8s environment variables.
    """
    return [k8s.V1EnvVar(name=name, value=value) for name, value in key_value_pairs]


def has_unscheduleable_pods(k8s_resource: Union[k8s.V1Job, k8s.V1Deployment]) -> bool:
    """Does a resource have unschedulable pods associated with it?

    :param k8s_resource: The Kubernetes resource managing the pods.
        For example, a Job or Deployment.
    :raises RuntimeError: If no pods managed by the resource can be found.
    :return: Boolean flag.
    """
    namespace = k8s_resource.metadata.namespace
    pod_base_name = k8s_resource.metadata.name

    k8s_pod_query = k8s.CoreV1Api().list_namespaced_pod(
        namespace=namespace,
    )
    k8s_pod_data = [
        e for e in k8s_pod_query.items if e.metadata.name.startswith(pod_base_name)
    ]
    if not k8s_pod_data:
        msg = (
            f"cannot find pods with names that start with {pod_base_name} in "
            f"namespace={namespace}"
        )
        raise RuntimeError(msg)
    try:
        unschedulable_pods = [
            pod.metadata.name
            for pod in k8s_pod_data
            if pod.status.conditions[0].reason == "Unschedulable"
        ]
        return True if unschedulable_pods else False
    except IndexError:
        return False


def check_resource_scheduling_status(
    resources: Union[Iterable[k8s.V1Job], Iterable[k8s.V1Deployment]]
) -> None:
    """Check job or deployment cluster scheduling status.

    :param resources: List of jobs or deployments to check.
    :raises BodyworkClusterResourcesError: if any resources cannot be
        scheduled onto a k8s cluster node.
    """
    unschedulable_pods = [has_unscheduleable_pods(resource) for resource in resources]
    if any(unschedulable_pods):
        resource_type = (
            "job" if isinstance(list(resources)[0], k8s.V1Job) else "deployment"
        )
        raise BodyworkClusterResourcesError(
            resource_type, [resource.metadata.name for resource in resources]
        )
