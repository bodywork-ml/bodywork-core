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
This module contains functions for helping with the creation of a
Kubernetes namespace with the necessary service accounts and roles to
run workflows, jobs and service deployments, securely. It is target at
being called from the CLI.
"""
from .terminal import print_info, print_warn
from .. import k8s
from ..constants import (
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
)


def is_namespace_available_for_bodywork(namespace: str) -> bool:
    """Is the namespace available for use by Bodywork.

    :param namespace: The namespace to check.
    :return: Boolean flag indicating the namespace's availability for
        running Bodywork projects.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return False
    workflow_controller_sa_exists = k8s.service_account_exists(
        namespace, BODYWORK_WORKFLOW_SERVICE_ACCOUNT
    )
    workflow_controller_sa_cluster_role_binding_exists = (
        k8s.cluster_role_binding_exists(
            k8s.workflow_cluster_role_binding_name(namespace)
        )
    )
    is_namespace_setup = (
        True
        if (
            workflow_controller_sa_exists
            and workflow_controller_sa_cluster_role_binding_exists
        )
        else False
    )
    if is_namespace_setup:
        return True
    else:
        if not workflow_controller_sa_exists:
            print_warn(
                f"Missing service-account={BODYWORK_WORKFLOW_SERVICE_ACCOUNT} from "
                f"namespace={namespace}."
            )
        if not workflow_controller_sa_cluster_role_binding_exists:
            print_warn(
                f"Missing cluster-role-binding="
                f"{k8s.workflow_cluster_role_binding_name(namespace)}."
            )
        return False


def setup_namespace_with_service_accounts_and_roles(namespace: str) -> None:
    """Setup kubernetes namespace for Bodywork Workflow accounts.

    If the namespace does not already exist, then it will be created
    first. Then the cluster/service accounts required by bodywork to
    run workflows will be created.

    Note, that to use this function the Kubernetes user running the
    command must be authorised to create namespaces, service accounts,
    roles and cluster-roles.

    :param namespace: Name of namespace.
    """
    if k8s.namespace_exists(namespace):
        print_warn(f"namespace={namespace} already exists.")
    else:
        print_info(f"Creating namespace={namespace}.")
        k8s.create_namespace(namespace)

    workflow_sa = BODYWORK_WORKFLOW_SERVICE_ACCOUNT
    workflow_crb = k8s.workflow_cluster_role_binding_name(namespace)
    if k8s.service_account_exists(namespace, workflow_sa):
        print_warn(
            f"service-account={workflow_sa} already exists in namespace={namespace}."
        )
    else:
        print_info(f"Creating service-account={workflow_sa} in namespace={namespace}.")
        print_info(f"Creating cluster-role-binding={workflow_crb}.")
        k8s.setup_workflow_service_accounts(namespace)
