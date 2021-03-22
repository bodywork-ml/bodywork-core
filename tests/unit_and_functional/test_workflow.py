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
Test Bodywork workflow execution.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Iterable

import requests
from pytest import raises
from _pytest.capture import CaptureFixture

from bodywork.config import BodyworkConfig
from bodywork.constants import STAGE_CONFIG_FILENAME, PROJECT_CONFIG_FILENAME
from bodywork.exceptions import (
    BodyworkMissingConfigError,
    BodyworkWorkflowExecutionError
)
from bodywork.stage import BatchStage, ServiceStage
from bodywork.workflow import (
    BodyworkProject,
    image_exists_on_dockerhub,
    parse_dockerhub_image_string,
    run_workflow,
    _parse_dag_definition,
    _get_workflow_stages,
    _print_logs_to_stdout
)


def test_parse_dag_definition_parses_multi_stage_dags():
    dag_definition = 'stage_1 >> stage_2,stage_3 >> stage_4'
    parsed_dag_structure = _parse_dag_definition(dag_definition)
    expected_dag_structure = [
        ['stage_1'],
        ['stage_2', 'stage_3'],
        ['stage_4']
    ]
    assert parsed_dag_structure == expected_dag_structure


def test_parse_dag_definition_parses_single_stage_dags():
    dag_definition = 'stage_1'
    parsed_dag_structure = _parse_dag_definition(dag_definition)
    expected_dag_structure = [['stage_1']]
    assert parsed_dag_structure == expected_dag_structure


def test_parse_dag_definition_raises_invalid_dag_definition_exceptions():
    dag_definition = 'stage_1 >> ,stage_3 >> stage_4'
    with raises(ValueError, match='null stages found in step 2'):
        _parse_dag_definition(dag_definition)


def test_get_workflow_stages_raises_exception_for_invalid_stages(
    project_repo_location: Path,
):
    dag = [['stage_1_good'], ['stage_2_bad_config']]
    with raises(RuntimeError, match='stage_2_bad_config'):
        _get_workflow_stages(dag, project_repo_location)


def test_get_workflow_stages_return_valid_stage_info(
    project_repo_location: Path,
):
    dag = [['stage_1_good'], ['stage_4_good', 'stage_5_good']]

    path_to_stage_1_dir = project_repo_location / 'stage_1_good'
    stage_1_info = BatchStage(
        'stage_1_good',
        BodyworkConfig(path_to_stage_1_dir / STAGE_CONFIG_FILENAME),
        path_to_stage_1_dir
    )

    path_to_stage_4_dir = project_repo_location / 'stage_4_good'
    stage_4_info = BatchStage(
        'stage_4_good',
        BodyworkConfig(path_to_stage_4_dir / STAGE_CONFIG_FILENAME),
        path_to_stage_4_dir
    )

    path_to_stage_5_dir = project_repo_location / 'stage_5_good'
    stage_5_info = ServiceStage(
        'stage_5_good',
        BodyworkConfig(path_to_stage_5_dir / STAGE_CONFIG_FILENAME),
        path_to_stage_5_dir
    )

    all_stage_info = _get_workflow_stages(dag, project_repo_location)
    assert len(all_stage_info) == 3
    assert all_stage_info['stage_1_good'] == stage_1_info
    assert all_stage_info['stage_4_good'] == stage_4_info
    assert all_stage_info['stage_5_good'] == stage_5_info


@patch('requests.Session')
def test_image_exists_on_dockerhub_handles_connection_error(
    mock_requests_session: MagicMock
):
    mock_requests_session().get.side_effect = requests.exceptions.ConnectionError
    with raises(RuntimeError, match='cannot connect to'):
        image_exists_on_dockerhub('bodywork-ml/bodywork-core', 'latest')


@patch('requests.Session')
def test_image_exists_on_dockerhub_handles_correctly_identifies_image_repos(
    mock_requests_session: MagicMock
):
    mock_requests_session().get.return_value = requests.Response()

    mock_requests_session().get.return_value.status_code = 200
    assert image_exists_on_dockerhub('bodywork-ml/bodywork-core', 'v1') is True

    mock_requests_session().get.return_value.status_code = 404
    assert image_exists_on_dockerhub('bodywork-ml/bodywork-core', 'x') is False


def test_parse_dockerhub_image_string_raises_exception_for_invalid_strings():
    with raises(
        ValueError,
        match=f'invalid DOCKER_IMAGE specified in {PROJECT_CONFIG_FILENAME}'
    ):
        parse_dockerhub_image_string('bodyworkml-bodywork-stage-runner:latest')
        parse_dockerhub_image_string('bodyworkml/bodywork-core:lat:st')


def test_parse_dockerhub_image_string_parses_valid_strings():
    assert (parse_dockerhub_image_string('bodyworkml/bodywork-core:0.0.1')
            == ('bodyworkml/bodywork-core', '0.0.1'))
    assert (parse_dockerhub_image_string('bodyworkml/bodywork-core')
            == ('bodyworkml/bodywork-core', 'latest'))


@patch('bodywork.workflow.k8s')
def test_run_workflow_raises_exception_if_namespace_does_not_exist(
    mock_k8s: MagicMock,
    setup_bodywork_test_project: Iterable[bool],
    project_repo_location: Path,
):
    mock_k8s.namespace_exists.return_value = False
    with raises(BodyworkWorkflowExecutionError, match='not a valid namespace'):
        run_workflow('foo_bar_foo_993', project_repo_location)


@patch('bodywork.workflow.k8s')
def test_print_logs_to_stdout(mock_k8s: MagicMock, capsys: CaptureFixture):
    mock_k8s.get_latest_pod_name.return_value = 'bodywork-test-project--stage-1'
    mock_k8s.get_pod_logs.return_value = 'foo-bar'
    _print_logs_to_stdout('the-namespace', 'bodywork-test-project--stage-1')
    captured_stdout = capsys.readouterr().out
    assert 'foo-bar' in captured_stdout

    mock_k8s.get_latest_pod_name.return_value = None
    _print_logs_to_stdout('the-namespace', 'bodywork-test-project--stage-1')
    captured_stdout = capsys.readouterr().out
    assert 'cannot get logs for bodywork-test-project--stage-1' in captured_stdout

    mock_k8s.get_latest_pod_name.side_effect = Exception
    _print_logs_to_stdout('the-namespace', 'bodywork-test-project--stage-1')
    captured_stdout = capsys.readouterr().out
    assert 'cannot get logs for bodywork-test-project--stage-1' in captured_stdout
