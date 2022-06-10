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
Unit tests for k8s API helper functions.
"""
from unittest.mock import MagicMock, Mock, patch

import kubernetes
from pytest import raises

from bodywork.exceptions import BodyworkClusterResourcesError
from bodywork.k8s.utils import (
    api_exception_msg,
    check_resource_scheduling_status,
    has_unscheduleable_pods,
    make_valid_k8s_name,
)


def test_api_exception_msg_retreives_message_str():
    mock_api_exception = Mock()

    mock_api_exception.body = '{"message": "foo"}'
    assert "foo" in api_exception_msg(mock_api_exception)

    mock_api_exception.body = '{"bar": "foo"}'
    assert api_exception_msg(mock_api_exception) == ""


@patch("kubernetes.client.CoreV1Api")
def test_has_unscheduleable_pods_correctly_identifies_bad_pod_condition(
    mock_k8s_core_api: MagicMock,
):
    mock_k8s_core_api().list_namespaced_pod.return_value = kubernetes.client.V1PodList(
        items=[
            kubernetes.client.V1Pod(
                metadata=kubernetes.client.V1ObjectMeta(
                    name="foo-123", namespace="bar"
                ),
                status=kubernetes.client.V1PodStatus(
                    conditions=[
                        kubernetes.client.V1PodCondition(
                            reason="Unschedulable", status="False", type="PodScheduled"
                        )
                    ]
                ),
            )
        ]
    )
    test_job = kubernetes.client.V1Job(
        metadata=kubernetes.client.V1ObjectMeta(name="foo", namespace="bar")
    )
    assert has_unscheduleable_pods(test_job)


@patch("kubernetes.client.CoreV1Api")
def test_has_unscheduleable_pods_correctly_identifies_good_pod_condition(
    mock_k8s_core_api: MagicMock,
):
    mock_k8s_core_api().list_namespaced_pod.return_value = kubernetes.client.V1PodList(
        items=[
            kubernetes.client.V1Pod(
                metadata=kubernetes.client.V1ObjectMeta(
                    name="foo-123", namespace="bar"
                ),
                status=kubernetes.client.V1PodStatus(conditions=[]),
            )
        ]
    )
    test_job = kubernetes.client.V1Job(
        metadata=kubernetes.client.V1ObjectMeta(name="foo", namespace="bar")
    )
    assert not has_unscheduleable_pods(test_job)


@patch("kubernetes.client.CoreV1Api")
def test_has_unscheduleable_pods_raises_error_if_pods_not_found(
    mock_k8s_core_api: MagicMock,
):
    mock_k8s_core_api().list_namespaced_pod.return_value = kubernetes.client.V1PodList(
        items=[]
    )
    test_job = kubernetes.client.V1Job(
        metadata=kubernetes.client.V1ObjectMeta(name="foo", namespace="bar")
    )
    with raises(RuntimeError, match="cannot find pods with names that start with"):
        has_unscheduleable_pods(test_job)


def test_make_valid_k8s_name_corrects_invalid_names():
    assert make_valid_k8s_name("a-valid-name") == "a-valid-name"
    assert make_valid_k8s_name(" an invalid_name ") == "an-invalid-name"


@patch("bodywork.k8s.utils.has_unscheduleable_pods")
def test_check_resource_scheduling_status_raises_error_if_pods_unschedulable(
    mock_has_unscheduleable_pods: MagicMock,
):
    mock_resource = Mock(spec=kubernetes.client.V1Deployment)
    mock_resource.metadata.name = "foo"
    mock_has_unscheduleable_pods.return_value = True
    with raises(BodyworkClusterResourcesError, match=r"Inadequate cluster cpu.+deploy"):
        check_resource_scheduling_status([mock_resource])

    mock_resource = Mock(spec=kubernetes.client.V1Job)
    mock_resource.metadata.name = "foo"
    mock_has_unscheduleable_pods.return_value = True
    with raises(BodyworkClusterResourcesError, match=r"Inadequate cluster cpu.+job"):
        check_resource_scheduling_status([mock_resource])
