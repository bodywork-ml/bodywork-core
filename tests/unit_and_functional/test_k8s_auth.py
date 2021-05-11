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
Unit tests for the high-level Kubernetes interface to the authentication
and authorisation APIs used to grant users and pods access to Kubernetes
resources.
"""
from unittest.mock import MagicMock, patch
from typing import Iterable

import kubernetes

from bodywork.constants import (
    BODYWORK_WORKFLOW_CLUSTER_ROLE,
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
)
from bodywork.k8s.auth import (
    cluster_role_exists,
    cluster_role_binding_exists,
    delete_cluster_role_binding,
    workflow_cluster_role_binding_name,
    load_kubernetes_config,
    service_account_exists,
    setup_job_and_deployment_service_accounts,
    setup_workflow_service_account,
)


@patch("kubernetes.config.load_incluster_config")
def test_load_kubernetes_config_loads_incluster_config_when_in_cluster(
    mock_k8s_load_incluster_config: MagicMock, k8s_env_vars: Iterable[bool]
):
    load_kubernetes_config()
    mock_k8s_load_incluster_config.assert_called_once()


@patch("kubernetes.config.load_kube_config")
def test_load_kubernetes_config_loads_kube_config_when_not_in_cluster(
    mock_k8s_load_kube_config: MagicMock,
):
    load_kubernetes_config()
    mock_k8s_load_kube_config.assert_called_once()


@patch("kubernetes.client.CoreV1Api")
def test_service_account_exists_identifies_existing_service_accounts(
    mock_k8s_core_api: MagicMock,
):
    mock_k8s_core_api().list_namespaced_service_account.return_value = (
        kubernetes.client.V1ServiceAccountList(
            items=[
                kubernetes.client.V1ServiceAccount(
                    metadata=kubernetes.client.V1ObjectMeta(
                        namespace="bodywork-dev", name="bodywork-sa"
                    )
                )
            ]
        )
    )
    assert service_account_exists("bodywork-dev", "bodywork-sa") is True
    assert service_account_exists("bodywork-dev", "foo-sa") is False


@patch("kubernetes.client.RbacAuthorizationV1Api")
def test_cluster_role_exists_identifies_existing_cluster_role(
    mock_k8s_rbac_api: MagicMock,
):
    mock_k8s_rbac_api().list_cluster_role.return_value = (
        kubernetes.client.V1alpha1ClusterRoleList(
            items=[
                kubernetes.client.V1ClusterRole(
                    metadata=kubernetes.client.V1ObjectMeta(name="cluster-role-1")
                ),
                kubernetes.client.V1ClusterRole(
                    metadata=kubernetes.client.V1ObjectMeta(name="cluster-role-2")
                ),
            ]
        )
    )
    assert cluster_role_exists("cluster-role-1") is True
    assert cluster_role_exists("cluster-role-0") is False


@patch("kubernetes.client.RbacAuthorizationV1Api")
def test_delete_cluster_role_binding_deletes_role_bindings(
    mock_k8s_rbac_api: MagicMock,
):
    delete_cluster_role_binding("xx-the-namespace")
    mock_k8s_rbac_api().delete_cluster_role_binding.assert_called_once_with(
        name="xx-the-namespace"
    )


@patch("kubernetes.client.RbacAuthorizationV1Api")
def test_cluster_role_binding_exists_exists_identifies_existing_cluster_role_binding(
    mock_k8s_rbac_api: MagicMock,
):
    mock_k8s_rbac_api().list_cluster_role_binding.return_value = (
        kubernetes.client.V1ClusterRoleBindingList(
            items=[
                kubernetes.client.V1ClusterRoleBinding(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name="cluster-role-binding-1"
                    ),
                    role_ref=kubernetes.client.V1RoleRef(
                        api_group="rbac.authorization.k8s.io",
                        kind="ClusterRole",
                        name="cluster-role-1",
                    ),
                    subjects=None,
                ),
                kubernetes.client.V1ClusterRoleBinding(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name="cluster-role-binding-2"
                    ),
                    role_ref=kubernetes.client.V1RoleRef(
                        api_group="rbac.authorization.k8s.io",
                        kind="ClusterRole",
                        name="cluster-role-2",
                    ),
                    subjects=None,
                ),
            ]
        )
    )
    assert cluster_role_binding_exists("cluster-role-binding-1") is True
    assert cluster_role_binding_exists("cluster-role-binding-0") is False


def test_workflow_cluster_role_binding_name():
    namespace = "bodywork-dev"
    expected_workflow_crb = f"{BODYWORK_WORKFLOW_CLUSTER_ROLE}--{namespace}"
    assert workflow_cluster_role_binding_name(namespace) == expected_workflow_crb


def test_setup_workflow_service_account_creates_service_accounts_and_roles():
    with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_api:
        with patch("kubernetes.client.RbacAuthorizationV1Api") as mock_k8s_rbac_api:
            mock_k8s_rbac_api().list_cluster_role.return_value = (
                kubernetes.client.V1alpha1ClusterRoleList(items=[])
            )
            mock_k8s_rbac_api().list_cluster_role_bindings.return_value = (
                kubernetes.client.V1ClusterRoleBindingList(items=[])
            )
            setup_workflow_service_account("bodywork-dev")
            mock_k8s_core_api().create_namespaced_service_account.assert_called_once()
            mock_k8s_rbac_api().create_namespaced_role.assert_called_once()
            mock_k8s_rbac_api().create_namespaced_role_binding.assert_called_once()
            mock_k8s_rbac_api().create_cluster_role.assert_called_once()
            mock_k8s_rbac_api().create_cluster_role_binding.assert_called_once()

    with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_api:
        with patch("kubernetes.client.RbacAuthorizationV1Api") as mock_k8s_rbac_api:
            mock_k8s_rbac_api().list_cluster_role.return_value = (
                kubernetes.client.V1alpha1ClusterRoleList(
                    items=[
                        kubernetes.client.V1ClusterRole(
                            metadata=kubernetes.client.V1ObjectMeta(
                                name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT
                            )
                        )
                    ]
                )
            )
            setup_workflow_service_account("bodywork-dev")
            mock_k8s_core_api().create_namespaced_service_account.assert_called_once()
            mock_k8s_rbac_api().create_namespaced_role.assert_called_once()
            mock_k8s_rbac_api().create_namespaced_role_binding.assert_called_once()
            mock_k8s_rbac_api().create_cluster_role.assert_not_called()
            mock_k8s_rbac_api().create_cluster_role_binding.assert_called_once()


def test_setup_job_and_deployment_service_account_creates_service_accounts_and_roles():
    with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_api:
        with patch("kubernetes.client.RbacAuthorizationV1Api") as mock_k8s_rbac_api:
            setup_job_and_deployment_service_accounts("bodywork-dev")
            mock_k8s_core_api().create_namespaced_service_account.assert_called_once()
            mock_k8s_rbac_api().create_namespaced_role.assert_called_once()
            mock_k8s_rbac_api().create_namespaced_role_binding.assert_called_once()
