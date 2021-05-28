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
This module contains functions for managing service deployments that have
been created as part of executed workflows.
"""
from .. import k8s


def display_service_deployments_in_namespace(namespace: str) -> None:
    """Print active service deployments to stdout.

    :param namespace: Namespace in which to look for deployments.
    """
    if not k8s.namespace_exists(namespace):
        print(f"namespace={namespace} could not be found on k8s cluster")
        return None
    service_deployments = k8s.list_service_stage_deployments(namespace)
    for name, data in service_deployments.items():
        print(
            f'\n{"-"*len(name)}-\n'
            f"{name}:\n"
            f'{"-"*len(name)}-\n'
            f'|- {"GIT_URL":<22}{data["git_url"]}\n'
            f'|- {"GIT_BRANCH":<22}{data["git_branch"]}\n'
            f'|- {"REPLICAS_AVAILABLE":<22}{str(data["available_replicas"])}\n'
            f'|- {"REPLICAS_UNAVAILABLE":<22}{str(data["unavailable_replicas"])}\n'
            f'|- {"EXPOSED_AS_SERVICE":<22}{data["service_exposed"]}\n'
            f'|- {"CLUSTER_SERVICE_URL":<22}{data["service_url"]}\n'
            f'|- {"CLUSTER_SERVICE_PORT":<22}{data["service_port"]}\n'
            f'|- {"INGRESS_CREATED":<22}{data["has_ingress"]}\n'
            f'|- {"INGRESS_ROUTE":<22}{data["ingress_route"]}\n'
        )


def delete_service_deployment_in_namespace(namespace: str, name: str) -> None:
    """Delete a service deployment from within a k8s namespace.

    :param namespace: The namespace in which the service deployment
        exists.
    :param name: The name of the service deployment to delete.
    """
    if not k8s.namespace_exists(namespace):
        print(f"namespace={namespace} could not be found on k8s cluster")
        return None
    if name not in k8s.list_service_stage_deployments(namespace).keys():
        print(f"deployment={name} not found in namespace={namespace}")
        return None
    k8s.delete_deployment(namespace, name)
    print(f"deployment={name} deleted from namespace={namespace}")
    if k8s.is_exposed_as_cluster_service(namespace, name):
        k8s.stop_exposing_cluster_service(namespace, name)
        print(
            f"service at {k8s.cluster_service_url(namespace, name)} "
            f"deleted from namespace={namespace}"
        )
    if k8s.has_ingress(namespace, name):
        k8s.delete_deployment_ingress(namespace, name)
        print(
            f"ingress route {k8s.ingress_route(namespace, name)} "
            f"deleted from namespace={namespace}"
        )
