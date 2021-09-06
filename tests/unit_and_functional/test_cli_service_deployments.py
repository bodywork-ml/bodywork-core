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
Test high-level service and deployment management functions.
"""
import re
from unittest.mock import MagicMock, patch

from _pytest.capture import CaptureFixture

from bodywork.cli.service_deployments import (
    delete_service_deployment_in_namespace,
    display_service_deployments,
)

Test_ServiceStageDeployment = {
    "bodywork-test-project--serve": {
        "service_url": "http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local",    # noqa
        "service_port": 5000,
        "service_exposed": "true",
        "available_replicas": 1,
        "unavailable_replicas": 0,
        "git_url": "project_repo_url",
        "git_branch": "project_repo_branch",
        "has_ingress": "true",
        "ingress_route": "/bodywork-dev/bodywork-test-project",
    }
}


@patch("bodywork.cli.service_deployments.k8s")
def test_display_service_deployments_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_service_deployments("bodywork-dev")
    captured_one = capsys.readouterr()
    assert "namespace=bodywork-dev could not be found" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = (
        Test_ServiceStageDeployment
    )
    display_service_deployments("bodywork-dev")
    captured_two = capsys.readouterr()
    assert re.findall(r"REPLICAS_AVAILABLE\s+1", captured_two.out)
    assert re.findall(r"REPLICAS_UNAVAILABLE\s+0", captured_two.out)
    assert re.findall(r"GIT_URL\s+project_repo_url", captured_two.out)
    assert re.findall(r"GIT_BRANCH\s+project_repo_branch", captured_two.out)
    assert re.findall(r"CLUSTER_SERVICE_PORT\s+5000", captured_two.out)
    assert re.findall(
        r"CLUSTER_SERVICE_URL\s+http://bodywork-test-project--serve.bodywork-dev.svc",
        captured_two.out,
    )
    assert re.findall(
        r"INGRESS_ROUTE\s+/bodywork-dev/bodywork-test-project", captured_two.out
    )


@patch("bodywork.cli.service_deployments.k8s")
def test_display_all_service_deployments(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    Test_ServiceStageDeployment["bodywork-test-project--second-service"] = {
        "service_url": "http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local",    # noqa
        "service_port": 6000,
        "service_exposed": "true",
        "available_replicas": 1,
        "unavailable_replicas": 0,
        "git_url": "project_repo_url",
        "git_branch": "project_repo_branch",
        "has_ingress": "true",
        "ingress_route": "/bodywork-dev/bodywork-test-project",
    }

    mock_k8s_module.list_service_stage_deployments.return_value = (
        Test_ServiceStageDeployment
    )
    display_service_deployments()
    captured_one = capsys.readouterr()
    assert re.findall(r"bodywork-test-project--serve", captured_one.out)
    assert re.findall(r"bodywork-test-project--second-service", captured_one.out)
    assert re.findall(r"CLUSTER_SERVICE_PORT\s+5000", captured_one.out)
    assert re.findall(r"CLUSTER_SERVICE_PORT\s+6000", captured_one.out)


@patch("bodywork.cli.service_deployments.k8s")
def test_display_service_deployment(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    Test_ServiceStageDeployment["bodywork-test-project--second-service"] = {
        "service_url": "http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local",    # noqa
        "service_port": 6000,
        "service_exposed": "true",
        "available_replicas": 1,
        "unavailable_replicas": 0,
        "git_url": "project_repo_url",
        "git_branch": "project_repo_branch",
        "has_ingress": "true",
        "ingress_route": "/bodywork-dev/bodywork-test-project",
    }
    mock_k8s_module.list_service_stage_deployments.return_value = (
        Test_ServiceStageDeployment
    )

    display_service_deployments(service_name="Missing-Service")

    captured_one = capsys.readouterr()
    assert re.findall(r"service: Missing-Service could not be found on k8s cluster", captured_one.out)  # noqa

    display_service_deployments(service_name="bodywork-test-project--serve")
    captured_two = capsys.readouterr()
    assert re.findall(r"bodywork-test-project--serve", captured_two.out)
    assert not re.findall(r"bodywork-test-project--second-service", captured_two.out)
    assert re.findall(r"CLUSTER_SERVICE_PORT\s+5000", captured_two.out)


@patch("bodywork.cli.service_deployments.k8s")
def test_delete_deployment_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    mock_k8s_module.list_service_stage_deployments.return_value = {"foo": {}}
    delete_service_deployment_in_namespace(
        "bodywork-dev", "bodywork-test-project--serve"
    )
    captured_one = capsys.readouterr()
    assert "namespace=bodywork-dev could not be found" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {"foo": {}}
    delete_service_deployment_in_namespace(
        "bodywork-dev", "bodywork-test-project--serve"
    )
    captured_two = capsys.readouterr()
    assert "deployment=bodywork-test-project--serve not found" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        "bodywork-test-project--serve": {}
    }

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        "bodywork-test-project--serve": {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = False
    delete_service_deployment_in_namespace(
        "bodywork-dev", "bodywork-test-project--serve"
    )
    captured_three = capsys.readouterr()
    assert "" in captured_three.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        "bodywork-test-project--serve": {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = True
    mock_k8s_module.stop_exposing_cluster_service.side_effect = None
    mock_k8s_module.cluster_service_url.return_value = (
        "http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local"
    )
    delete_service_deployment_in_namespace(
        "bodywork-dev", "bodywork-test-project--serve"
    )
    captured_four = capsys.readouterr()
    assert (
        "http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local deleted"
        in captured_four.out
    )

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        "bodywork-test-project--serve": {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = False
    mock_k8s_module.stop_exposing_cluster_service.side_effect = None
    mock_k8s_module.has_ingress.return_value = False
    delete_service_deployment_in_namespace(
        "bodywork-dev", "bodywork-test-project--serve"
    )
    captured_five = capsys.readouterr()
    assert "" in captured_five.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        "bodywork-test-project--serve": {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = False
    mock_k8s_module.stop_exposing_cluster_service.side_effect = None
    mock_k8s_module.has_ingress.return_value = True
    mock_k8s_module.delete_deployment_ingress.side_effect = None
    mock_k8s_module.ingress_route.return_value = (
        "/bodywork-dev/bodywork-test-project--serve"
    )
    delete_service_deployment_in_namespace(
        "bodywork-dev", "bodywork-test-project--serve"
    )
    captured_six = capsys.readouterr()
    assert (
        "ingress route /bodywork-dev/bodywork-test-project--serve" in captured_six.out
    )
