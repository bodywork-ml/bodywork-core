"""
Unit tests for the high-level Kubernetes pod-logs interface, used to
retreive pod logs.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import kubernetes

from bodywork.k8s.pod_logs import get_latest_pod_name, get_pod_logs


@patch('kubernetes.client.CoreV1Api')
def test_get_latest_pod_name_return_latest_pod_name(
    mock_k8s_core_api: MagicMock,
):
    mock_k8s_core_api().list_namespaced_pod.return_value = kubernetes.client.V1PodList(
        items=[
            kubernetes.client.V1Pod(
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace='the-namespace',
                    name='bodywork--stage-1-abcdefg'
                ),
                status=kubernetes.client.V1PodStatus(
                    start_time=datetime(2020, 10, 1, 12, 0, 0)
                )
            ),
            kubernetes.client.V1Pod(
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace='the-namespace',
                    name='bodywork--stage-1-hijmlmn'
                ),
                status=kubernetes.client.V1PodStatus(
                    start_time=datetime(2020, 10, 1, 12, 0, 1)
                )
            ),
            kubernetes.client.V1Pod(
                metadata=kubernetes.client.V1ObjectMeta(
                    namespace='the-namespace',
                    name='bodywork--stage-2-opqrstu'
                ),
                status=kubernetes.client.V1PodStatus(
                    start_time=datetime(2020, 10, 1, 12, 0, 0)
                )
            )
        ]
    )

    assert get_latest_pod_name('the-namespace', 'bodywork--stage-0') is None
    assert (get_latest_pod_name('the-namespace', 'bodywork--stage-1')
            == 'bodywork--stage-1-hijmlmn')


@patch('kubernetes.client.CoreV1Api')
def test_get_pod_logs_returns_pod_logs(
    mock_k8s_core_api: MagicMock,
):
    mock_k8s_core_api().read_namespaced_pod_log.return_value = """
    2020-10-08 10:36:49,319 - INFO - cli.stage - attempting to run
    git version 2.20.1
    Cloning into 'bodywork_project'...
    Collecting flask==1.1.2
    """
    pod_logs = get_pod_logs('the-namespace', 'bodywork--stage-1-abcdefg')
    assert '2020-10-08 10:36:49,319 - INFO' in pod_logs
    assert 'Collecting flask==1.1.2' in pod_logs
