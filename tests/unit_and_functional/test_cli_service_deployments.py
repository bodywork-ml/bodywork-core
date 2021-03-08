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
from unittest.mock import MagicMock, patch

from _pytest.capture import CaptureFixture

from bodywork.cli.service_deployments import (
    delete_service_deployment_in_namespace,
    display_service_deployments_in_namespace
)


@patch('bodywork.cli.service_deployments.k8s')
def test_display_service_deployments_in_namespace(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_service_deployments_in_namespace('bodywork-dev')
    captured_one = capsys.readouterr()
    assert 'namespace=bodywork-dev could not be found' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    service_url = 'http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local'
    mock_k8s_module.list_service_stage_deployments.return_value = {
        'bodywork-test-project--serve': {
            'service_url': service_url,
            'service_port': 5000,
            'service_exposed': 'true',
            'available_replicas': 1,
            'unavailable_replicas': 0,
            'git_url': 'project_repo_url',
            'git_branch': 'project_repo_branch',
            'has_ingress': 'true',
            'ingress_route': '/bodywork-dev/bodywork-test-project'
        }
    }
    display_service_deployments_in_namespace('bodywork-dev')
    captured_two = capsys.readouterr()
    assert 'http://bodywork-test-project--serve.bodywork-dev.svc' in captured_two.out
    assert '5000' in captured_two.out
    assert '1' in captured_two.out
    assert '0' in captured_two.out
    assert 'project_repo_url' in captured_two.out
    assert 'project_repo_branch' in captured_two.out
    assert '/bodywork-dev/bodywork-test-project' in captured_two.out


@patch('bodywork.cli.service_deployments.k8s')
def test_delete_deployment_in_namespace(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    mock_k8s_module.list_service_stage_deployments.return_value = {'foo': {}}
    delete_service_deployment_in_namespace(
        'bodywork-dev',
        'bodywork-test-project--serve'
    )
    captured_one = capsys.readouterr()
    assert 'namespace=bodywork-dev could not be found' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {'foo': {}}
    delete_service_deployment_in_namespace(
        'bodywork-dev',
        'bodywork-test-project--serve'
    )
    captured_two = capsys.readouterr()
    assert 'deployment=bodywork-test-project--serve not found' in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        'bodywork-test-project--serve': {}
    }

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        'bodywork-test-project--serve': {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = False
    delete_service_deployment_in_namespace(
        'bodywork-dev',
        'bodywork-test-project--serve'
    )
    captured_three = capsys.readouterr()
    assert '' in captured_three.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        'bodywork-test-project--serve': {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = True
    mock_k8s_module.stop_exposing_cluster_service.side_effect = None
    mock_k8s_module.cluster_service_url.return_value = (
        'http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local'
    )
    delete_service_deployment_in_namespace(
        'bodywork-dev',
        'bodywork-test-project--serve'
    )
    captured_four = capsys.readouterr()
    assert ('http://bodywork-test-project--serve.bodywork-dev.svc.cluster.local deleted'
            in captured_four.out)

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        'bodywork-test-project--serve': {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = False
    mock_k8s_module.stop_exposing_cluster_service.side_effect = None
    mock_k8s_module.has_ingress.return_value = False
    delete_service_deployment_in_namespace(
        'bodywork-dev',
        'bodywork-test-project--serve'
    )
    captured_five = capsys.readouterr()
    assert '' in captured_five.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_service_stage_deployments.return_value = {
        'bodywork-test-project--serve': {}
    }
    mock_k8s_module.delete_deployment.side_effect = None
    mock_k8s_module.is_exposed_as_cluster_service.return_value = False
    mock_k8s_module.stop_exposing_cluster_service.side_effect = None
    mock_k8s_module.has_ingress.return_value = True
    mock_k8s_module.delete_deployment_ingress.side_effect = None
    mock_k8s_module.ingress_route.return_value = (
        '/bodywork-dev/bodywork-test-project--serve'
    )
    delete_service_deployment_in_namespace(
        'bodywork-dev',
        'bodywork-test-project--serve'
    )
    captured_six = capsys.readouterr()
    assert 'ingress route /bodywork-dev/bodywork-test-project--serve' in captured_six.out
