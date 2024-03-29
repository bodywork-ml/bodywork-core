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
Unit tests for the high-level Kubernetes jobs interface, used to
orchestrate the execution of service deployment stages.
"""
from copy import deepcopy
from datetime import datetime
from unittest.mock import call, MagicMock, Mock, patch

import kubernetes
import copy
from pytest import fixture, raises

from bodywork.exceptions import BodyworkClusterResourcesError
from bodywork.k8s.deployments import (
    cluster_service_url,
    configure_service_stage_deployment,
    create_deployment,
    create_deployment_ingress,
    delete_all_namespace_deployments,
    delete_deployment,
    delete_deployment_ingress,
    deployment_id,
    DeploymentStatus,
    expose_deployment_as_cluster_service,
    has_ingress,
    ingress_route,
    is_existing_deployment,
    is_exposed_as_cluster_service,
    _get_deployment_status,
    list_service_stage_deployments,
    monitor_deployments_to_completion,
    rollback_deployment,
    stop_exposing_cluster_service,
    update_deployment,
)


@fixture(scope="session")
def service_stage_deployment_object() -> kubernetes.client.V1Deployment:
    container_resources = kubernetes.client.V1ResourceRequirements(
        requests={"cpu": "0.5", "memory": "250M"}
    )
    container = kubernetes.client.V1Container(
        name="bodywork",
        image="bodyworkml/bodywork-core:latest",
        image_pull_policy="Always",
        resources=container_resources,
        command=["bodywork", "stage"],
        args=["project_repo_url", "project_repo_branch", "myservice"],
    )
    pod_spec = kubernetes.client.V1PodSpec(
        containers=[container], restart_policy="Never"
    )
    pod_template_spec = kubernetes.client.V1PodTemplateSpec(
        metadata=kubernetes.client.V1ObjectMeta(
            annotations={"last-updated": "2020-09-03T15:08:41.836365"},
        ),
        spec=pod_spec,
    )
    deployment_spec = kubernetes.client.V1DeploymentSpec(
        replicas=2,
        template=pod_template_spec,
        selector={"matchLabels": {"stage": "myservice"}},
    )
    deployment_metadata = kubernetes.client.V1ObjectMeta(
        namespace="bodywork-dev",
        name="myservice",
        annotations={"port": "5000"},
        labels={
            "app": "bodywork",
            "stage": "myservice",
            "deployment-name": "myproject",
            "git-commit-hash": "abc123",
            "git-branch": "project_repo_branch",
        },
    )
    deployment = kubernetes.client.V1Deployment(
        metadata=deployment_metadata, spec=deployment_spec
    )
    return deployment


def test_configure_service_stage_deployment():
    deployment = configure_service_stage_deployment(
        namespace="bodywork-dev",
        stage_name="serve",
        project_name="bodywork-test-project",
        project_repo_url="bodywork-ml/bodywork-test-project",
        git_commit_hash="xyz123",
        project_repo_branch="dev",
        image="bodyworkml/bodywork-core:latest",
        replicas=2,
        cpu_request=1,
        memory_request=100,
        startup_time_seconds=5,
    )
    assert deployment.metadata.namespace == "bodywork-dev"
    assert deployment.metadata.name == "serve"
    assert deployment.spec.replicas == 2

    containers = deployment.spec.template.spec.containers
    assert containers[0].args == [
        "bodywork-ml/bodywork-test-project",
        "serve",
        "--branch=dev",
    ]
    assert containers[0].image == "bodyworkml/bodywork-core:latest"
    assert containers[0].resources.requests["cpu"] == "1"
    assert containers[0].resources.requests["memory"] == "100M"
    assert containers[0].startup_probe.tcp_socket.port == 80
    assert containers[0].startup_probe.period_seconds == 10
    assert containers[0].startup_probe.failure_threshold == 1
    assert containers[0].liveness_probe.period_seconds == 10


@patch("kubernetes.client.AppsV1Api")
def test_create_deployment_tries_to_create_deployment_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    create_deployment(service_stage_deployment_object)
    mock_k8s_apps_api().create_namespaced_deployment.assert_called_once_with(
        body=service_stage_deployment_object, namespace="bodywork-dev"
    )


@patch("kubernetes.client.AppsV1Api")
def test_is_existing_deployment_correctly_filters_deployments(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_k8s_apps_api().list_namespaced_deployment.side_effect = [
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(name="myservice")
                )
            ]
        ),
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(name="some-other-stage")
                )
            ]
        ),
    ]

    service_stage_namespace = service_stage_deployment_object.metadata.namespace
    service_stage_name = service_stage_deployment_object.metadata.name
    assert is_existing_deployment(service_stage_namespace, service_stage_name) is True
    assert is_existing_deployment(service_stage_namespace, service_stage_name) is False


@patch("kubernetes.client.AppsV1Api")
def test_update_deployment_tries_to_update_deployment_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    update_deployment(service_stage_deployment_object)
    mock_k8s_apps_api().patch_namespaced_deployment.assert_called_once_with(
        body=service_stage_deployment_object,
        name="myservice",
        namespace="bodywork-dev",
    )


@patch("kubernetes.client.AppsV1Api")
def test_rollback_deployment_tries_to_patch_deployment_to_force_rollback(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    template_spec_revision_one = deepcopy(service_stage_deployment_object.spec.template)
    template_spec_revision_one.metadata.annotations["last-updated"] = datetime(
        2020, 11, 6, 7
    ).isoformat()

    template_spec_revision_two = deepcopy(service_stage_deployment_object.spec.template)
    template_spec_revision_two.metadata.annotations["last-updated"] = datetime(
        2020, 11, 6, 8
    ).isoformat()

    mock_k8s_apps_api().list_namespaced_replica_set.return_value = (
        kubernetes.client.V1ReplicaSetList(
            items=[
                kubernetes.client.V1ReplicaSet(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name=f"{service_stage_deployment_object.metadata.name}-1234",
                        namespace=service_stage_deployment_object.metadata.namespace,
                        annotations={
                            "deployment.kubernetes.io/revision": "1",
                            "port": "5000",
                        },
                    ),
                    spec=kubernetes.client.V1ReplicaSetSpec(
                        selector=kubernetes.client.V1LabelSelector(
                            match_labels={"stage": "my-app"}
                        ),
                        template=template_spec_revision_one,
                    ),
                ),
                kubernetes.client.V1ReplicaSet(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name=f"{service_stage_deployment_object.metadata.name}-5678",
                        namespace=service_stage_deployment_object.metadata.namespace,
                        annotations={
                            "deployment.kubernetes.io/revision": "2",
                            "port": "5000",
                        },
                    ),
                    spec=kubernetes.client.V1ReplicaSetSpec(
                        selector=kubernetes.client.V1LabelSelector(
                            match_labels={"stage": "my-app"}
                        ),
                        template=template_spec_revision_two,
                    ),
                ),
            ]
        )
    )

    rollback_deployment(service_stage_deployment_object)
    mock_k8s_apps_api().patch_namespaced_deployment.assert_called_once_with(
        name=service_stage_deployment_object.metadata.name,
        namespace=service_stage_deployment_object.metadata.namespace,
        body=[
            {
                "op": "replace",
                "path": "/spec/template",
                "value": template_spec_revision_one,
            },
            {
                "op": "replace",
                "path": "/metadata/annotations",
                "value": {"deployment.kubernetes.io/revision": "1", "port": "5000"},
            },
        ],
    )


@patch("kubernetes.client.AppsV1Api")
@patch("bodywork.k8s.deployments.delete_deployment")
def test_rollback_deployment_tries_to_delete_new_deployments(
    mock_delete_deployment: MagicMock,
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    template_spec_revision_one = deepcopy(service_stage_deployment_object.spec.template)
    template_spec_revision_one.metadata.annotations["last-updated"] = datetime(
        2020, 11, 6, 7
    ).isoformat()

    mock_k8s_apps_api().list_namespaced_replica_set.return_value = (
        kubernetes.client.V1ReplicaSetList(
            items=[
                kubernetes.client.V1ReplicaSet(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name=f"{service_stage_deployment_object.metadata.name}-1234",
                        namespace=service_stage_deployment_object.metadata.namespace,
                        annotations={
                            "deployment.kubernetes.io/revision": "1",
                            "port": "5000",
                        },
                    ),
                    spec=kubernetes.client.V1ReplicaSetSpec(
                        selector=kubernetes.client.V1LabelSelector(
                            match_labels={"stage": "my-app"}
                        ),
                        template=template_spec_revision_one,
                    ),
                ),
            ]
        )
    )

    rollback_deployment(service_stage_deployment_object)
    namespace = service_stage_deployment_object.metadata.namespace
    name = service_stage_deployment_object.metadata.name
    mock_delete_deployment.assert_called_once_with(namespace, name)


@patch("kubernetes.client.AppsV1Api")
def test_delete_deployment_tries_to_delete_deployment_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    delete_deployment(
        service_stage_deployment_object.metadata.namespace,
        service_stage_deployment_object.metadata.name,
    )
    mock_k8s_apps_api().delete_namespaced_deployment.assert_called_once_with(
        body=kubernetes.client.V1DeleteOptions(propagation_policy="Background"),
        name="myservice",
        namespace="bodywork-dev",
    )


@patch("kubernetes.client.AppsV1Api")
def test_delete_all_namespace_deployments_tries_to_delete_deployments_with_k8s_api(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = (
        kubernetes.client.V1JobList(  # noqa
            items=[service_stage_deployment_object, service_stage_deployment_object]
        )
    )
    delete_all_namespace_deployments("bodywork-dev")
    mock_k8s_apps_api().delete_namespaced_deployment.assert_has_calls(
        [
            call(
                body=kubernetes.client.V1DeleteOptions(propagation_policy="Background"),
                name="myservice",
                namespace="bodywork-dev",
            ),
            call(
                body=kubernetes.client.V1DeleteOptions(propagation_policy="Background"),
                name="myservice",
                namespace="bodywork-dev",
            ),
        ]
    )


@patch("kubernetes.client.AppsV1Api")
def test_get_deployment_status_correctly_determines_complete_status(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = (
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(name="myservice"),
                    status=kubernetes.client.V1DeploymentStatus(
                        available_replicas=1, unavailable_replicas=None
                    ),
                )
            ]
        )
    )
    assert (
        _get_deployment_status(service_stage_deployment_object)
        == DeploymentStatus.ACTIVE
    )


@patch("kubernetes.client.AppsV1Api")
def test_get_deployment_status_raises_exception_when_status_cannot_be_determined(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = (
        kubernetes.client.V1DeploymentList(
            items=[
                kubernetes.client.V1Deployment(
                    metadata=kubernetes.client.V1ObjectMeta(name="myservice"),
                    status=kubernetes.client.V1DeploymentStatus(
                        available_replicas=0, unavailable_replicas=0
                    ),
                )
            ]
        )
    )
    with raises(RuntimeError, match="cannot determine status for deployment"):
        _get_deployment_status(service_stage_deployment_object)


@patch("kubernetes.client.AppsV1Api")
def test_get_deployment_status_raises_exception_when_deployment_cannot_be_found(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_k8s_apps_api().list_namespaced_deployment.return_value = (
        kubernetes.client.V1DeploymentList(items=[])
    )
    with raises(RuntimeError):
        _get_deployment_status(service_stage_deployment_object)


@patch("bodywork.k8s.deployments._get_deployment_status")
@patch("bodywork.k8s.deployments.check_resource_scheduling_status")
def test_monitor_deployments_raises_timeout_error_if_jobs_do_not_succeed(
    mock_check_resource_scheduling_status: MagicMock,
    mock_deployment_status: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_deployment_status.return_value = DeploymentStatus.PROGRESSING
    with raises(TimeoutError, match="have yet to reach status=complete"):
        monitor_deployments_to_completion(
            [service_stage_deployment_object], timeout_seconds=1
        )


@patch("bodywork.k8s.deployments._get_deployment_status")
@patch("bodywork.k8s.deployments.check_resource_scheduling_status")
def test_monitor_deployments_identifies_successful_deployments(
    mock_check_resource_scheduling_status: MagicMock,
    mock_deployment_status: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_deployment_status.side_effect = [
        DeploymentStatus.PROGRESSING,
        DeploymentStatus.PROGRESSING,
        DeploymentStatus.ACTIVE,
        DeploymentStatus.ACTIVE,
    ]
    successful = monitor_deployments_to_completion(
        [service_stage_deployment_object, service_stage_deployment_object],
        timeout_seconds=1,
        polling_freq_seconds=0.5,
    )
    assert successful is True


@patch("bodywork.k8s.deployments.check_resource_scheduling_status")
@patch("bodywork.k8s.deployments.update_progress_bar")
@patch("bodywork.k8s.deployments._get_deployment_status")
def test_monitor_deployments_to_completion_updates_progress_bar(
    mock_deployment_status: MagicMock,
    mock_update_progress_bar: MagicMock,
    mock_update_check_resource_scheduling_status: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    mock_deployment_status.side_effect = [
        DeploymentStatus.PROGRESSING,
        DeploymentStatus.ACTIVE,
    ]
    monitor_deployments_to_completion(
        [service_stage_deployment_object], 1, 0.5, progress_bar=None
    )
    mock_update_progress_bar.assert_not_called()

    mock_deployment_status.side_effect = [
        DeploymentStatus.PROGRESSING,
        DeploymentStatus.ACTIVE,
    ]
    mock_progress_bar = Mock()
    monitor_deployments_to_completion(
        [service_stage_deployment_object], 1, 0.5, progress_bar=mock_progress_bar
    )
    mock_update_progress_bar.assert_called()


def test_deployment_id_creates_valid_deployed_service_identifiers():
    assert deployment_id("x", "y") == "x/y"


def test_list_service_stage_deployments_returns_service_stage_info(
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    deployment_name = service_stage_deployment_object.metadata.labels["deployment-name"]
    service_namespace = service_stage_deployment_object.metadata.namespace
    service_name = service_stage_deployment_object.metadata.name
    service_url = f"http://{service_name}.{service_namespace}.svc.cluster.local"
    service_port = service_stage_deployment_object.metadata.annotations["port"]

    service_stage_deployment_object.status = kubernetes.client.V1DeploymentStatus(
        available_replicas=1, unavailable_replicas=None
    )

    service_stage_service_object = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(
            namespace=service_namespace, name=service_name
        )
    )

    service_stage_ingress_object = kubernetes.client.V1Ingress(
        metadata=kubernetes.client.V1ObjectMeta(
            namespace=service_namespace,
            name=service_name,
            annotations={
                "kubernetes.io/ingress.class": "nginx",
                "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                "bodywork": "true",
            },
        )
    )

    with patch("kubernetes.client.AppsV1Api") as mock_k8s_apps_api:
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_api:
            with patch("kubernetes.client.NetworkingV1Api") as mock_k8s_ext_api:
                mock_k8s_apps_api().list_namespaced_deployment.return_value = (
                    kubernetes.client.V1DeploymentList(
                        items=[service_stage_deployment_object]
                    )
                )
                mock_k8s_core_api().list_namespaced_service.return_value = (
                    kubernetes.client.V1ServiceList(
                        items=[service_stage_service_object]
                    )
                )
                mock_k8s_ext_api().list_namespaced_ingress.return_value = (
                    kubernetes.client.V1IngressList(
                        items=[service_stage_ingress_object]
                    )
                )
                deployment_info = list_service_stage_deployments(service_namespace)
                mock_k8s_apps_api().list_namespaced_deployment.assert_called_with(
                    namespace=service_namespace, label_selector="app=bodywork"
                )
                deployment_id = f"{deployment_name}/{service_name}"
                assert deployment_id in deployment_info.keys()
                assert deployment_info[deployment_id]["service_url"] == service_url
                assert deployment_info[deployment_id]["service_port"] == service_port
                assert deployment_info[deployment_id]["service_exposed"] is True
                assert deployment_info[deployment_id]["available_replicas"] == 1
                assert deployment_info[deployment_id]["unavailable_replicas"] == 0
                assert (
                    deployment_info[deployment_id]["git_branch"]
                    == "project_repo_branch"
                )
                assert deployment_info[deployment_id]["git_url"] == "project_repo_url"
                assert deployment_info[deployment_id]["git_commit_hash"] == "abc123"
                assert deployment_info[deployment_id]["has_ingress"] is True


@patch("kubernetes.client.AppsV1Api")
def test_list_service_stage_deployments_returns_all_services_on_cluster(
    mock_k8s_apps_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    service_namespace = service_stage_deployment_object.metadata.namespace
    service_name = service_stage_deployment_object.metadata.name

    service_stage_deployment_object.status = kubernetes.client.V1DeploymentStatus(
        available_replicas=1, unavailable_replicas=None
    )

    service_stage_deployment_object2 = copy.deepcopy(service_stage_deployment_object)
    service_stage_deployment_object2.metadata.name = "myservice"
    service_stage_deployment_object2.metadata.namespace = "abc"
    service_stage_deployment_object2.metadata.labels["deployment-name"] = "myproject2"

    service_stage_service_object = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(
            namespace=service_namespace, name=service_name
        )
    )

    service_stage_service_object_2 = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(namespace="abc", name="myservice")
    )

    service_stage_ingress_object = kubernetes.client.V1Ingress(
        metadata=kubernetes.client.V1ObjectMeta(
            namespace=service_namespace,
            name=service_name,
            annotations={
                "kubernetes.io/ingress.class": "nginx",
                "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                "bodywork": "true",
            },
        )
    )

    with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_api:
        with patch("kubernetes.client.NetworkingV1Api") as mock_k8s_ext_api:
            mock_k8s_apps_api().list_deployment_for_all_namespaces.return_value = (
                kubernetes.client.V1DeploymentList(
                    items=[
                        service_stage_deployment_object,
                        service_stage_deployment_object2,
                    ]
                )
            )
            mock_k8s_core_api().list_namespaced_service.side_effect = [
                kubernetes.client.V1ServiceList(items=[service_stage_service_object]),
                kubernetes.client.V1ServiceList(items=[service_stage_service_object_2]),
            ]
            mock_k8s_ext_api().list_namespaced_ingress.return_value = (
                kubernetes.client.V1IngressList(items=[service_stage_ingress_object])
            )
            deployment_info = list_service_stage_deployments()
            mock_k8s_apps_api().list_deployment_for_all_namespaces.assert_called_once()
            assert "myproject/myservice" in deployment_info.keys()
            assert "myproject2/myservice" in deployment_info.keys()


def test_cluster_service_url(
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    namespace = service_stage_deployment_object.metadata.namespace
    name = service_stage_deployment_object.metadata.namespace
    assert (
        cluster_service_url(namespace, name)
        == f"http://{name}.{namespace}.svc.cluster.local"
    )


@patch("kubernetes.client.CoreV1Api")
def test_expose_deployment_as_cluster_service_tries_to_expose_deployment_as_service(
    mock_k8s_core_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):
    service_object = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(
            namespace="bodywork-dev",
            name="myservice",
            labels={"app": "bodywork", "stage": "myservice"},
        ),
        spec=kubernetes.client.V1ServiceSpec(
            type="ClusterIP",
            selector={"stage": "myservice"},
            ports=[kubernetes.client.V1ServicePort(port=5000, target_port=5000)],
        ),
    )

    expose_deployment_as_cluster_service(service_stage_deployment_object)
    mock_k8s_core_api().create_namespaced_service.assert_called_once_with(
        namespace=service_stage_deployment_object.metadata.namespace,
        body=service_object,
    )


@patch("kubernetes.client.CoreV1Api")
def test_is_exposed_as_cluster_service_identifies_existing_services(
    mock_k8s_core_api: MagicMock,
):
    mock_k8s_core_api().list_namespaced_service.side_effect = [
        kubernetes.client.V1ServiceList(
            items=[
                kubernetes.client.V1Service(
                    metadata=kubernetes.client.V1ObjectMeta(name="bodywork--serve")
                )
            ]
        ),
        kubernetes.client.V1ServiceList(
            items=[
                kubernetes.client.V1Service(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name="some-other-project--serve"
                    )
                )
            ]
        ),
    ]
    assert is_exposed_as_cluster_service("bodywork-dev", "bodywork--serve") is True
    assert is_exposed_as_cluster_service("bodywork-dev", "bodywork--serve") is False


@patch("kubernetes.client.CoreV1Api")
def test_stop_exposing_cluster_service_tries_to_stop_exposing_deployment_as_service(
    mock_k8s_core_api: MagicMock,
):
    stop_exposing_cluster_service("bodywork-dev", "myservice")
    mock_k8s_core_api().delete_namespaced_service.assert_called_once_with(
        namespace="bodywork-dev",
        name="myservice",
        propagation_policy="Background",
    )


def test_ingress_route(service_stage_deployment_object: kubernetes.client.V1Deployment):
    namespace = service_stage_deployment_object.metadata.namespace
    name = service_stage_deployment_object.metadata.namespace
    assert ingress_route(namespace, name) == f"/{namespace}/{name}"


@patch("kubernetes.client.NetworkingV1Api")
def test_create_deployment_ingress_tries_to_create_ingress_resource(
    mock_k8s_networking_api: MagicMock,
    service_stage_deployment_object: kubernetes.client.V1Deployment,
):

    ingress_spec = kubernetes.client.V1IngressSpec(
        rules=[
            kubernetes.client.V1IngressRule(
                http=kubernetes.client.V1HTTPIngressRuleValue(
                    paths=[
                        kubernetes.client.V1HTTPIngressPath(
                            path="/bodywork-dev/myservice(/|$)(.*)",
                            path_type="Exact",
                            backend=kubernetes.client.V1IngressBackend(
                                service=kubernetes.client.V1IngressServiceBackend(
                                    name="myservice",
                                    port=kubernetes.client.V1ServiceBackendPort(
                                        number=5000
                                    ),
                                )
                            ),
                        )
                    ]
                )
            )
        ]
    )

    ingress_object = kubernetes.client.V1Ingress(
        metadata=kubernetes.client.V1ObjectMeta(
            namespace="bodywork-dev",
            name="myservice",
            annotations={
                "kubernetes.io/ingress.class": "nginx",
                "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
            },
            labels={"app": "bodywork", "stage": "myservice"},
        ),
        spec=ingress_spec,
    )

    create_deployment_ingress(service_stage_deployment_object)
    mock_k8s_networking_api().create_namespaced_ingress.assert_called_once_with(
        namespace="bodywork-dev", body=ingress_object
    )


@patch("kubernetes.client.NetworkingV1Api")
def test_delete_deployment_ingress_tries_to_deletes_ingress_resource(
    mock_k8s_networking_api: MagicMock,
):
    delete_deployment_ingress("bodywork-dev", "myservice")
    mock_k8s_networking_api().delete_namespaced_ingress.assert_called_once_with(
        namespace="bodywork-dev",
        name="myservice",
        propagation_policy="Background",
    )


@patch("kubernetes.client.NetworkingV1Api")
def test_has_ingress_identifies_existing_ingress_resources(
    mock_k8s_networking_api: MagicMock,
):
    mock_k8s_networking_api().list_namespaced_ingress.side_effect = [
        kubernetes.client.V1IngressList(
            items=[
                kubernetes.client.V1Ingress(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name="bodywork--serve",
                        annotations={"kubernetes.io/ingress.class": "nginx"},
                        labels={"app": "bodywork", "stage": "bodywork--serve"},
                    )
                )
            ]
        ),
        kubernetes.client.V1IngressList(
            items=[
                kubernetes.client.V1Ingress(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name="bodywork--some-other-service",
                        annotations={"kubernetes.io/ingress.class": "nginx"},
                        labels={"app": "bodywork", "stage": "bodywork--serve"},
                    )
                )
            ]
        ),
    ]
    assert has_ingress("bodywork-dev", "bodywork--serve") is True
    assert has_ingress("bodywork-dev", "bodywork--serve") is False
