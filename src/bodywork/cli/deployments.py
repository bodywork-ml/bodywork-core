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
from .terminal import print_dict, print_info, print_warn
from .. import k8s


def display_deployments(
    namespace: str = None,
    name: str = None,
    service_name: str = None,
) -> None:
    """Print active deployments to stdout.

    :param namespace: Namespace in which to look for deployments.
    :param name: Name of the deployment to display.
    :param service_name: Name of service to display.
    """
    if namespace and not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster")
        return None
    deployments = k8s.list_service_stage_deployments(namespace, name)
    if not deployments:
        print("No deployments found")
        return None
    if service_name:
        if service_name not in deployments:
            print_warn(f"Could not find service={service_name}.")
            return None
        print_dict(deployments[service_name], service_name)
    else:
        table_data = {
            name: data["git_url"] for name, data in deployments.items()
        }
        print_dict(table_data, "services", "Name", "Git Repository URL")


def delete_service_deployment_in_namespace(namespace: str, name: str) -> None:
    """Delete a service deployment from within a k8s namespace.

    :param namespace: The namespace in which the service deployment
        exists.
    :param name: The name of the service deployment to delete.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if name not in k8s.list_service_stage_deployments(namespace).keys():
        print_warn(f"Could not find service={name}.")
        return None
    k8s.delete_deployment(namespace, name)
    print_info(f"Deleted service={name}.")
    if k8s.is_exposed_as_cluster_service(namespace, name):
        k8s.stop_exposing_cluster_service(namespace, name)
        print_info(
            f"Stopped exposing service at {k8s.cluster_service_url(namespace, name)}"
        )
    if k8s.has_ingress(namespace, name):
        k8s.delete_deployment_ingress(namespace, name)
        print_info(
            f"Deleted ingress to service at {k8s.ingress_route(namespace, name)}"
        )


def delete_deployment(deployment_name) -> None:
    """Delete a deployment by deleting the namespace it's in.

    :param deployment_name: The name of the deployment.
    """
    if not k8s.namespace_exists(deployment_name):
        print_info(f"deployment={deployment_name} could not be found on k8s cluster.")
        return None
    k8s.delete_namespace(deployment_name)
    print_info(f"deployment={deployment_name} deleted.")
