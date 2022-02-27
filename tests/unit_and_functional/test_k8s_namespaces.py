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
Unit tests for the high-level Kubernetes interface used to manage
Kubernetes namespaces.
"""
from unittest.mock import MagicMock, patch

import kubernetes

from bodywork.k8s.namespaces import create_namespace, delete_namespace, namespace_exists


@patch("kubernetes.client.CoreV1Api")
def test_namespace_exists_identifies_existing_namespaces(mock_k8s_core_api: MagicMock):
    mock_k8s_core_api().list_namespace.return_value = kubernetes.client.V1NamespaceList(
        items=[
            kubernetes.client.V1Namespace(
                metadata=kubernetes.client.V1ObjectMeta(name="bodywork-dev")
            ),
            kubernetes.client.V1Namespace(
                metadata=kubernetes.client.V1ObjectMeta(name="not-a-real-namespace")
            ),
        ]
    )
    assert namespace_exists("bodywork-dev") is True
    assert namespace_exists("foo-bar-la-la-la") is False


@patch("kubernetes.client.CoreV1Api")
def test_create_namespace_creates_namespaces(mock_k8s_core_api: MagicMock):
    create_namespace("bodywork-dev")
    mock_k8s_core_api().create_namespace.assert_called_once_with(
        body=kubernetes.client.V1Namespace(
            metadata=kubernetes.client.V1ObjectMeta(name="bodywork-dev")
        )
    )


@patch("kubernetes.client.CoreV1Api")
def test_delete_namespace_deletes_namespaces(mock_k8s_core_api: MagicMock):
    delete_namespace("bodywork-dev")
    mock_k8s_core_api().delete_namespace.assert_called_once_with(
        name="bodywork-dev", propagation_policy="Background"
    )
