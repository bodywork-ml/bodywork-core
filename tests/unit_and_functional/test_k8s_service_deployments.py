# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020  Bodywork Machine Learning Ltd.

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
Unit tests for the high-level Kubernetes jobs interface, used to
orchestrate the execution of service deployment stages.
"""
from copy import deepcopy
from datetime import datetime
from unittest.mock import call, MagicMock, patch

import kubernetes
from pytest import fixture, raises

from bodywork.k8s.service_deployments import (
    configure_service_stage_deployment,
    create_deployment,
    delete_all_namespace_deployments,
    delete_deployment,
    DeploymentStatus,
    expose_deployment_as_cluster_service,
    is_existing_deployment,
    is_exposed_as_cluster_service,
    _get_deployment_status,
    list_service_stage_deployments,
    monitor_deployments_to_completion,
    rollback_deployment,
    stop_exposing_cluster_service,
    update_deployment
)


@fixture(scope='session')
def service_stage_deployment_object() -> kubernetes.client.V1Deployment:
    container_resources = kubernetes.client.V1ResourceRequirements(
        requests={'cpu': '0.5', 'memory': '250M'}
    )
    container = kubernetes.client.V1Container(
        name='bodywork',
        image='bodyworkml/bodywork-core:latest',
        image_pull_policy='Always',
        resources=container_resources,
        command=['bodywork', 'stage'],
        args=['project_repo_url', 'project_repo_branch', 'serve']
    )
    pod_spec = kubernetes.client.V1PodSpec(
        containers=[container],
        restart_policy='Never'
    )
    pod_template_spec = kubernetes.client.V1PodTemplateSpec(
        metadata=kubernetes.client.V1ObjectMeta(
            labels={'app': 'bodywork-test-project--serve'},
            annotations={'last-updated': '2020-09-03T15:08:41.836365'}
        ),
        spec=pod_spec
    )
    deployment_spec = kubernetes.client.V1DeploymentSpec(
        replicas=2,
        template=pod_template_spec,
        selector={'matchLabels': {'app': 'bodywork-test-project--serve'}}
    )
    deployment_metadata = kubernetes.client.V1ObjectMeta(
        namespace='bodywork-dev',
        name='bodywork-test-project--serve',
        annotations={'port': '5000'}
    )
    deployment = kubernetes.client.V1Deployment(
        metadata=deployment_metadata,
        spec=deployment_spec
    )
    return deployment


def test_configure_service_stage_deployment():
    deployment = configure_service_stage_deployment(
        namespace='bodywork-dev',
        stage_name='serve',
        project_name='bodywork-test-project',
        project_repo_url='bodywork-ml/bodywork-test-project',
        project_repo_branch='dev',
        image='bodyworkml/bodywork-core:latest',
        replicas=2,
        cpu_request=1,
        memory_request=100,
        seconds_to_be_ready_before_completing=5
    )
    assert deployment.metadata.namespace == 'bodywork-dev'
    assert deployment.metadata.name == 'bodywork-test-project--serve'
    assert deployment.spec.replicas == 2
    assert (deployment.spec.template.spec.containers[0].args
            == ['bodywork-ml/bodywork-test-project', 'dev', 'serve'])
    assert (deployment.spec.template.spec.containers[0].image
            == 'bodyworkml/bodywork-core:latest')
    assert (deployment.spec.template.spec.containers[0].resources.requests['cpu']
            == '1')
    assert (deployment.spec.template.spec.containers[0].resources.requests['memory']
            == '100M')
    assert deployment.spec.min_ready_seconds == 5


@patch('kubernetes.client.AppsV1Api')
def test_create_deployment_tries_to_create_deployment_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    create_deployment(service_stage_deployment_object)
    mock_k8s_apps_api().create_namespaced_deployment.assert_called_once_with(
        body=service_stage_deployment_object,
        namespace='bodywork-dev'
    )


@patch('kubernetes.client.AppsV1Api')
def test_is_existing_deployment_correctly_filters_deployments(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    mock_k8s_apps_api().list_namespaced_deployment.side_effect = [
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='bodywork-test-project--serve'
                    )
                )
            ]
        ),
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(name='some-other-stage')
                )
            ]
        )
    ]

    service_stage_namespace = service_stage_deployment_object.metadata.namespace
    service_stage_name = service_stage_deployment_object.metadata.name
    assert is_existing_deployment(service_stage_namespace, service_stage_name) is True
    assert is_existing_deployment(service_stage_namespace, service_stage_name) is False


@patch('kubernetes.client.AppsV1Api')
def test_update_deployment_tries_to_update_deployment_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    update_deployment(service_stage_deployment_object)
    mock_k8s_apps_api().patch_namespaced_deployment.assert_called_once_with(
        body=service_stage_deployment_object,
        name='bodywork-test-project--serve',
        namespace='bodywork-dev'
    )


@patch('kubernetes.client.AppsV1Api')
def test_rollback_deployment_tries_to_patch_deployment_to_force_rollback(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    template_spec_revision_one = deepcopy(service_stage_deployment_object.spec.template)
    template_spec_revision_one.metadata.annotations['last-updated'] = (
        datetime(2020, 11, 6, 7).isoformat()
    )

    template_spec_revision_two = deepcopy(service_stage_deployment_object.spec.template)
    template_spec_revision_two.metadata.annotations['last-updated'] = (
        datetime(2020, 11, 6, 8).isoformat()
    )

    mock_k8s_apps_api().list_namespaced_replica_set.return_value = (
        kubernetes.client.V1ReplicaSetList(
            items=[
                kubernetes.client.V1ReplicaSet(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name=f'{service_stage_deployment_object.metadata.name}-1234',
                        namespace=service_stage_deployment_object.metadata.namespace,
                        annotations={
                            'deployment.kubernetes.io/revision': '1',
                            'port': '5000'
                        }
                    ),
                    spec=kubernetes.client.V1ReplicaSetSpec(
                        selector=kubernetes.client.V1LabelSelector(
                            match_labels={'app': 'my-app'}
                        ),
                        template=template_spec_revision_one
                    )
                ),
                kubernetes.client.V1ReplicaSet(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name=f'{service_stage_deployment_object.metadata.name}-5678',
                        namespace=service_stage_deployment_object.metadata.namespace,
                        annotations={
                            'deployment.kubernetes.io/revision': '2',
                            'port': '5000'
                        }
                    ),
                    spec=kubernetes.client.V1ReplicaSetSpec(
                        selector=kubernetes.client.V1LabelSelector(
                            match_labels={'app': 'my-app'}
                        ),
                        template=template_spec_revision_two
                    )
                )
            ]
        )
    )

    rollback_deployment(service_stage_deployment_object)
    mock_k8s_apps_api().patch_namespaced_deployment.assert_called_once_with(
        name=service_stage_deployment_object.metadata.name,
        namespace=service_stage_deployment_object.metadata.namespace,
        body=[
            {
                'op': 'replace',
                'path': '/spec/template',
                'value': template_spec_revision_one
            },
            {
                'op': 'replace',
                'path': '/metadata/annotations',
                'value': {
                    'deployment.kubernetes.io/revision': '1',
                    'port': '5000'
                }
            }
        ]
    )


@patch('kubernetes.client.AppsV1Api')
def test_delete_deployment_tries_to_delete_deployment_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    delete_deployment(
        service_stage_deployment_object.metadata.namespace,
        service_stage_deployment_object.metadata.name
    )
    mock_k8s_apps_api().delete_namespaced_deployment.assert_called_once_with(
        body=kubernetes.client.V1DeleteOptions(propagation_policy='Background'),
        name='bodywork-test-project--serve',
        namespace='bodywork-dev'
    )


@patch('kubernetes.client.AppsV1Api')
def test_delete_all_namespace_deployments_tries_to_delete_deployments_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = kubernetes.client.V1JobList(  # noqa
        items=[service_stage_deployment_object, service_stage_deployment_object]
    )
    delete_all_namespace_deployments('bodywork-dev')
    mock_k8s_apps_api().delete_namespaced_deployment.assert_has_calls([
        call(
            body=kubernetes.client.V1DeleteOptions(propagation_policy='Background'),
            name='bodywork-test-project--serve',
            namespace='bodywork-dev'
        ),
        call(
            body=kubernetes.client.V1DeleteOptions(propagation_policy='Background'),
            name='bodywork-test-project--serve',
            namespace='bodywork-dev'
        )
    ])


@patch('kubernetes.client.AppsV1Api')
def test__get_deployment_status_correctly_determines_complete_status(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = (
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='bodywork-test-project--serve'
                    ),
                    status=kubernetes.client.V1DeploymentStatus(
                        available_replicas=1,
                        unavailable_replicas=None
                    )
                )
            ]
        )
    )
    assert (_get_deployment_status(service_stage_deployment_object)
            == DeploymentStatus.COMPLETE)


@patch('kubernetes.client.AppsV1Api')
def test__get_deployment_status_raises_exception_when_status_cannot_be_determined(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = (
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='bodywork-test-project--serve'
                    ),
                    status=kubernetes.client.V1DeploymentStatus(
                        available_replicas=0,
                        unavailable_replicas=0
                    )
                )
            ]
        )
    )
    with raises(RuntimeError, match='cannot determine status for deployment'):
        _get_deployment_status(service_stage_deployment_object)


@patch('kubernetes.client.AppsV1Api')
def test_get_deployment_status_raises_exception_when_deployment_cannot_be_found(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = (
        kubernetes.client.V1DeploymentList(items=[])
    )
    with raises(RuntimeError):
        _get_deployment_status(service_stage_deployment_object)


@patch('bodywork.k8s.service_deployments._get_deployment_status')
def test_monitor_deployments_to_completion_raises_timeout_error_if_jobs_do_not_succeed(
    mock_deployment_status: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    mock_deployment_status.return_value = DeploymentStatus.PROGRESSING
    with raises(TimeoutError, match='have yet to reach status=complete'):
        monitor_deployments_to_completion(
            [service_stage_deployment_object],
            timeout_seconds=1
        )


@patch('bodywork.k8s.service_deployments._get_deployment_status')
def test_monitor_deployments_to_completion_identifies_successful_deployments(
    mock_deployment_status: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_deployment_status.side_effect = [
        DeploymentStatus.PROGRESSING,
        DeploymentStatus.PROGRESSING,
        DeploymentStatus.COMPLETE,
        DeploymentStatus.COMPLETE
    ]
    successful = monitor_deployments_to_completion(
        [service_stage_deployment_object, service_stage_deployment_object],
        timeout_seconds=1,
        polling_freq_seconds=0.5
    )
    assert successful is True


@patch('kubernetes.client.AppsV1Api')
def test_list_service_stage_deployments_returns_service_stage_info(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    service_stage_deployment_object.status = kubernetes.client.V1DeploymentStatus(
        available_replicas=1,
        unavailable_replicas=None
    )

    with patch('kubernetes.client.AppsV1Api') as mock_k8s_apps_api:
        with patch('kubernetes.client.CoreV1Api') as mock_k8s_core_api:
            mock_k8s_apps_api().list_namespaced_deployment.return_value = (
                kubernetes.client.V1DeploymentList(
                    items=[service_stage_deployment_object]
                )
            )
            mock_k8s_core_api().list_namespaced_service.return_value = (
                kubernetes.client.V1ServiceList(
                    items=[
                        kubernetes.client.V1Service(
                            metadata=kubernetes.client.V1ObjectMeta(
                                name='bodywork-test-project--serve'
                            )
                        )
                    ]
                )
            )

            deployment_info = list_service_stage_deployments('bodywork-dev')
            assert 'bodywork-test-project--serve' in deployment_info.keys()
            assert deployment_info['bodywork-test-project--serve']['service_url'] == 'http://bodywork-test-project--serve:5000'  # noqa
            assert deployment_info['bodywork-test-project--serve']['service_exposed'] == 'true'  # noqa
            assert deployment_info['bodywork-test-project--serve']['available_replicas'] == 1  # noqa
            assert deployment_info['bodywork-test-project--serve']['unavailable_replicas'] == 0  # noqa
            assert deployment_info['bodywork-test-project--serve']['git_branch'] == 'project_repo_branch'  # noqa
            assert deployment_info['bodywork-test-project--serve']['git_url'] == 'project_repo_url'  # noqa


@patch('kubernetes.client.CoreV1Api')
def test_expose_deployment_as_cluster_service_tries_to_expose_deployment_as_service(
    mock_k8s_core_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    service_object = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(
            namespace='bodywork-dev',
            name='bodywork-test-project--serve'
        ),
        spec=kubernetes.client.V1ServiceSpec(
            type='ClusterIP',
            selector={'app': 'bodywork-test-project--serve'},
            ports=[kubernetes.client.V1ServicePort(port=5000, target_port=5000)]
        )
    )

    expose_deployment_as_cluster_service(service_stage_deployment_object)
    mock_k8s_core_api().create_namespaced_service.assert_called_once_with(
        namespace=service_stage_deployment_object.metadata.namespace,
        body=service_object
    )


@patch('kubernetes.client.CoreV1Api')
def test_is_exposed_as_cluster_service_identifies_existing_services(
    mock_k8s_core_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment
):
    mock_k8s_core_api().list_namespaced_service.side_effect = [
        kubernetes.client.V1ServiceList(
            items=[
                kubernetes.client.V1Service(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='bodywork--serve'
                    )
                )
            ]
        ),
        kubernetes.client.V1ServiceList(
            items=[
                kubernetes.client.V1Service(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='some-other-project--serve'
                    )
                )
            ]
        )
    ]
    assert is_exposed_as_cluster_service('bodywork-dev', 'bodywork--serve') is True
    assert is_exposed_as_cluster_service('bodywork-dev', 'bodywork--serve') is False


@patch('kubernetes.client.CoreV1Api')
def test_stop_exposing_cluster_service_tries_to_stop_exposing_deployment_as_service(
    mock_k8s_core_api: MagicMock
):
    stop_exposing_cluster_service('bodywork-dev', 'bodywork-test-project--serve')
    mock_k8s_core_api().delete_namespaced_service.assert_called_once_with(
        namespace='bodywork-dev',
        name='bodywork-test-project--serve',
        propagation_policy='Background'
    )
