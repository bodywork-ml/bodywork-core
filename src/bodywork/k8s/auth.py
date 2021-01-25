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
High-level interface to the Kubernetes APIs used to manage
authentication and authorisation for cluster resources.
"""
import os

from kubernetes import client as k8s, config as k8s_config

from ..constants import (
    BODYWORK_WORKFLOW_CLUSTER_ROLE,
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
    BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
)


def load_kubernetes_config() -> None:
    """Attempt to load k8s config from file.

    If running within a k8s cluster, then KUBERNETES_SERVICE_HOST will
    be present, which allows us to call a special initialization method
    for in-cluster situations. Otherwise the standard ~/.kube/config is
    read.

    :raises RuntimeError: if a kubeconfig cannot be loaded.
    """
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        k8s_config.load_incluster_config()
    else:
        k8s_config.load_kube_config()


def service_account_exists(namespace: str, name: str) -> bool:
    """Does the service-account exist within the namespace.

    :param namespace: Kubernetes namespace to check.
    :param name: The name of the service-account to check.
    :return: True if the service-account was found, othewise False.
    """
    service_account_objects = (
        k8s.CoreV1Api()
        .list_namespaced_service_account(
            namespace=namespace
        )
        .items
    )
    service_account_names = [
        service_account_object.metadata.name
        for service_account_object in service_account_objects
    ]
    return True if name in service_account_names else False


def cluster_role_exists(name: str) -> bool:
    """Does the cluster-role exist.

    :param name: The name of the cluster-role to check.
    :return: True if the cluster-role was found, othewise False.
    """
    cluster_role_objects = (
        k8s.RbacAuthorizationV1Api()
        .list_cluster_role()
        .items
    )
    cluster_role_names = [
        cluster_role_object.metadata.name
        for cluster_role_object in cluster_role_objects
    ]
    return True if name in cluster_role_names else False


def workflow_cluster_role_binding_name(namespace: str) -> str:
    """Get cluster-role-binding name for workflow service-account.

    :param namespace: The namespace in which a workflow service-account
        has been deployed to.
    :return: The name assigned to the cluster-role-binding that
        associates the workflow cluster-role to the workflow
        service-account, within a namespace setup for Bodywork.
    """
    return f'{BODYWORK_WORKFLOW_CLUSTER_ROLE}--{namespace}'


def cluster_role_binding_exists(name: str) -> bool:
    """Does the cluster-role-binding exist.

    :param name: The name of the cluster-role-binding to check.
    :return: True if the cluster-role-binding was found, othewise False.
    """
    cluster_role_binding_objects = (
        k8s.RbacAuthorizationV1Api()
        .list_cluster_role_binding()
        .items
    )
    cluster_role_binding_names = [
        cluster_role_binding_object.metadata.name
        for cluster_role_binding_object in cluster_role_binding_objects
    ]
    return True if name in cluster_role_binding_names else False


def delete_cluster_role_binding(name: str) -> None:
    """Delete a cluster-role-binding.

    :param name: The name assigned to the cluster-role-binding.
    """
    k8s.RbacAuthorizationV1Api().delete_cluster_role_binding(
        name=name
    )


def setup_workflow_service_account(namespace: str) -> None:
    """Setup a workflow controller service-account with required roles.

    :param namespace: Namespace in which the service-account will be
        placed.
    """
    service_account_object = k8s.V1ServiceAccount(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT
        )
    )
    k8s.CoreV1Api().create_namespaced_service_account(
        namespace=namespace,
        body=service_account_object
    )

    role_object = k8s.V1Role(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT
        ),
        rules=[
            k8s.V1PolicyRule(
                api_groups=[''],
                resources=['*'],
                verbs=['*']
            ),
            k8s.V1PolicyRule(
                api_groups=['apps', 'batch'],
                resources=['*'],
                verbs=['*']
            )
        ]
    )
    k8s.RbacAuthorizationV1Api().create_namespaced_role(
        namespace=namespace,
        body=role_object
    )

    role_binding_object = k8s.V1RoleBinding(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT
        ),
        role_ref=k8s.V1RoleRef(
            kind='Role',
            name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
            api_group='rbac.authorization.k8s.io'
        ),
        subjects=[
            k8s.V1Subject(
                kind='ServiceAccount',
                name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
                namespace=namespace
            )
        ]
    )
    k8s.RbacAuthorizationV1Api().create_namespaced_role_binding(
        namespace=namespace,
        body=role_binding_object
    )

    if not cluster_role_exists(BODYWORK_WORKFLOW_CLUSTER_ROLE):
        cluster_role_object = k8s.V1ClusterRole(
            metadata=k8s.V1ObjectMeta(
                name=BODYWORK_WORKFLOW_CLUSTER_ROLE
            ),
            rules=[
                k8s.V1PolicyRule(
                    api_groups=[''],
                    resources=['namespaces'],
                    verbs=['get', 'list']
                ),
                k8s.V1PolicyRule(
                    api_groups=['rbac.authorization.k8s.io'],
                    resources=['clusterrolebindings'],
                    verbs=['get', 'list']
                )
            ]
        )
        k8s.RbacAuthorizationV1Api().create_cluster_role(
            body=cluster_role_object
        )

    if not cluster_role_binding_exists(workflow_cluster_role_binding_name(namespace)):
        cluster_role_binding_object = k8s.V1ClusterRoleBinding(
            metadata=k8s.V1ObjectMeta(
                name=workflow_cluster_role_binding_name(namespace),
                namespace=namespace
            ),
            role_ref=k8s.V1RoleRef(
                kind='ClusterRole',
                name=BODYWORK_WORKFLOW_CLUSTER_ROLE,
                api_group='rbac.authorization.k8s.io'
            ),
            subjects=[
                k8s.V1Subject(
                    kind='ServiceAccount',
                    name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
                    namespace=namespace
                )
            ]
        )
        k8s.RbacAuthorizationV1Api().create_cluster_role_binding(
            body=cluster_role_binding_object
        )


def setup_job_and_deployment_service_accounts(namespace: str) -> None:
    """Setup a jobs-and-deployments service-account with required roles.

    :param namespace: Namespace in which the service-account will be
        placed.
    """
    service_account_object = k8s.V1ServiceAccount(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
        )
    )
    k8s.CoreV1Api().create_namespaced_service_account(
        namespace=namespace,
        body=service_account_object
    )

    role_object = k8s.V1Role(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
        ),
        rules=[
            k8s.V1PolicyRule(
                api_groups=[''],
                resources=['secrets', 'configmaps'],
                verbs=['get', 'list']
            )
        ]
    )
    k8s.RbacAuthorizationV1Api().create_namespaced_role(
        namespace=namespace,
        body=role_object
    )

    role_binding_object = k8s.V1RoleBinding(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
        ),
        role_ref=k8s.V1RoleRef(
            kind='Role',
            name=BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT,
            api_group='rbac.authorization.k8s.io'
        ),
        subjects=[
            k8s.V1Subject(
                kind='ServiceAccount',
                name=BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT,
                namespace=namespace
            )
        ]
    )
    k8s.RbacAuthorizationV1Api().create_namespaced_role_binding(
        namespace=namespace,
        body=role_binding_object
    )
