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
This module contains functions for helping with the creation of a
Kubernetes namespace with the necessary service accounts and roles to
run workflows, jobs and service deployments, securely. It is target at
being called from the CLI.
"""
from .. import k8s
from ..constants import (
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
    BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
)


def is_namespace_available_for_bodywork(namespace: str) -> bool:
    """Is the namespace available for use by Bodywork.

    :param namespace: The namespace to check.
    :return: Boolean flag indicating the namespace's availability for
        running Bodywork projects.
    """
    if not k8s.namespace_exists(namespace):
        print(f'namespace={namespace} does not exist')
        return False
    workflow_controller_sa_exists = k8s.service_account_exists(
        namespace,
        BODYWORK_WORKFLOW_SERVICE_ACCOUNT
    )
    workflow_controller_sa_cluster_role_binding_exists = k8s.cluster_role_binding_exists(
        k8s.workflow_cluster_role_binding_name(namespace)
    )
    jobs_and_deployments_sa_exists = k8s.service_account_exists(
        namespace,
        BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
    )
    is_namespace_setup = (
        True
        if (workflow_controller_sa_exists
            and workflow_controller_sa_cluster_role_binding_exists
            and jobs_and_deployments_sa_exists)
        else False
    )
    if is_namespace_setup:
        print(f'namespace={namespace} is setup for use by Bodywork')
        return True
    else:
        if not workflow_controller_sa_exists:
            print(f'service-account={BODYWORK_WORKFLOW_SERVICE_ACCOUNT} is '
                  f'missing from namespace={namespace}')
        if not workflow_controller_sa_cluster_role_binding_exists:
            print(f'cluster-role-binding='
                  f'{k8s.workflow_cluster_role_binding_name(namespace)} is missing')
        if not jobs_and_deployments_sa_exists:
            print(f'service-account={BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT} is '
                  f'missing from namespace={namespace}')
        return False


def setup_namespace_with_service_accounts_and_roles(namespace: str) -> None:
    """Setup kubernetes namespace for use with Bodywork.

    If the namespace does not already exist, then it will be created
    first. Then, the service accounts and associated roles required by
    Bodywork containers will be created.

    Note, that to use this function the Kubernetes user running the
    command must be authrised to create namespaces, service accounts,
    roles and cluster-roles.

    :param namespace: Name of namespace.
    """
    if k8s.namespace_exists(namespace):
        print(f'namespace={namespace} already exists')
    else:
        print(f'creating namespace={namespace}')
        k8s.create_namespace(namespace)

    workflow_sa = BODYWORK_WORKFLOW_SERVICE_ACCOUNT
    workflow_crb = k8s.workflow_cluster_role_binding_name(namespace)
    if k8s.service_account_exists(namespace, workflow_sa):
        print(f'service-account={workflow_sa} already exists in namespace={namespace}')
    else:
        print(f'creating service-account={workflow_sa} in '
              f'namespace={namespace}')
        print(f'creating cluster-role-binding={workflow_crb}')
        k8s.setup_workflow_service_account(namespace)

    jobs_deps_sa = BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
    if k8s.service_account_exists(namespace, jobs_deps_sa):
        print(f'service-account={jobs_deps_sa} already exists in namespace={namespace}')
    else:
        print(f'creating service-account={jobs_deps_sa} in '
              f'namespace={namespace}')
        k8s.setup_job_and_deployment_service_accounts(namespace)
