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
from unittest.mock import MagicMock, patch, ANY
from typing import Iterable, Dict, Any

import requests
from pytest import raises
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture
from kubernetes import client as k8sclient

from bodywork.constants import (
    PROJECT_CONFIG_FILENAME,
    GIT_COMMIT_HASH_K8S_ENV_VAR,
    USAGE_STATS_SERVER_URL,
    FAILURE_EXCEPTION_K8S_ENV_VAR,
)
from bodywork.exceptions import (
    BodyworkWorkflowExecutionError,
    BodyworkDockerImageError,
    BodyworkGitError,
)
from bodywork.workflow_execution import (
    image_exists_on_dockerhub,
    parse_dockerhub_image_string,
    run_workflow,
    _print_logs_to_stdout,
)
from bodywork.config import BodyworkConfig


@patch("requests.Session")
def test_image_exists_on_dockerhub_handles_connection_error(
    mock_requests_session: MagicMock,
):
    mock_requests_session().get.side_effect = requests.exceptions.ConnectionError
    with raises(BodyworkDockerImageError, match="cannot connect to"):
        image_exists_on_dockerhub("bodywork-ml/bodywork-core", "latest")


@patch("requests.Session")
def test_image_exists_on_dockerhub_handles_correctly_identifies_image_repos(
    mock_requests_session: MagicMock,
):
    mock_requests_session().get.return_value = requests.Response()

    mock_requests_session().get.return_value.status_code = 200
    assert image_exists_on_dockerhub("bodywork-ml/bodywork-core", "v1") is True

    mock_requests_session().get.return_value.status_code = 404
    assert image_exists_on_dockerhub("bodywork-ml/bodywork-core", "x") is False


def test_parse_dockerhub_image_string_raises_exception_for_invalid_strings():
    with raises(
        BodyworkDockerImageError,
        match=f"Invalid Docker image specified: bodyworkml",
    ):
        parse_dockerhub_image_string("bodyworkml-bodywork-stage-runner:latest")
        parse_dockerhub_image_string("bodyworkml/bodywork-core:lat:st")


def test_parse_dockerhub_image_string_parses_valid_strings():
    assert parse_dockerhub_image_string("bodyworkml/bodywork-core:0.0.1") == (
        "bodyworkml/bodywork-core",
        "0.0.1",
    )
    assert parse_dockerhub_image_string("bodyworkml/bodywork-core") == (
        "bodyworkml/bodywork-core",
        "latest",
    )


@patch("bodywork.workflow_execution.BodyworkConfig")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.k8s")
def test_run_workflow_raises_exception_if_cannot_setup_namespace(
    mock_k8s: MagicMock,
    mock_git: MagicMock,
    mock_config: MagicMock,
    setup_bodywork_test_project: Iterable[bool],
    project_repo_location: Path,
):
    mock_config.logging.log_level = "DEBUG"

    git_url = f"file://{project_repo_location.absolute()}"
    mock_k8s.namespace_exists.return_value = False
    mock_k8s.create_namespace.side_effect = k8sclient.ApiException
    with raises(BodyworkWorkflowExecutionError, match="Unable to setup namespace"):
        run_workflow(git_url, config=mock_config)


@patch("bodywork.workflow_execution.k8s")
def test_print_logs_to_stdout(
    mock_k8s: MagicMock, capsys: CaptureFixture, caplog: LogCaptureFixture
):
    mock_k8s.get_latest_pod_name.return_value = "bodywork-test-project--stage-1"
    mock_k8s.get_pod_logs.return_value = "foo-bar"
    _print_logs_to_stdout("the-namespace", "bodywork-test-project--stage-1")
    captured_stdout = capsys.readouterr().out
    assert "foo-bar" in captured_stdout

    mock_k8s.get_latest_pod_name.return_value = None
    _print_logs_to_stdout("the-namespace", "bodywork-test-project--stage-1")
    captured_logs = caplog.text
    assert "Cannot get logs for bodywork-test-project--stage-1" in captured_logs

    caplog.clear()
    mock_k8s.get_latest_pod_name.side_effect = Exception
    _print_logs_to_stdout("the-namespace", "bodywork-test-project--stage-1")
    captured_logs = caplog.text
    assert "Cannot get logs for bodywork-test-project--stage-1" in captured_logs


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_run_workflow_adds_git_commit_to_batch_and_service_env_vars(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_requests: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    commit_hash = "MY GIT COMMIT HASH"
    mock_git_hash.return_value = commit_hash
    expected_result = [
        k8sclient.V1EnvVar(name=GIT_COMMIT_HASH_K8S_ENV_VAR, value=commit_hash)
    ]
    mock_k8s.create_k8s_environment_variables.return_value = expected_result
    mock_k8s.configure_env_vars_from_secrets.return_value = []
    config_path = Path(f"{project_repo_location}/bodywork.yaml")

    run_workflow(
        "foo_bar_foo_993",
        project_repo_location,
        config=BodyworkConfig(config_path),
    )

    mock_k8s.configure_service_stage_deployment.assert_called_once_with(
        ANY,
        ANY,
        ANY,
        ANY,
        ANY,
        ANY,
        replicas=ANY,
        port=ANY,
        container_env_vars=expected_result,
        image=ANY,
        cpu_request=ANY,
        memory_request=ANY,
        seconds_to_be_ready_before_completing=ANY,
    )
    mock_k8s.configure_batch_stage_job.assert_called_with(
        ANY,
        ANY,
        ANY,
        ANY,
        ANY,
        retries=ANY,
        container_env_vars=expected_result,
        image=ANY,
        cpu_request=ANY,
        memory_request=ANY,
    )


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_run_workflow_runs_failure_stage_on_failure(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_requests: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)
    config.project.run_on_failure = "on_fail_stage"

    error_message = "Test Error"
    mock_job = MagicMock(k8sclient.V1Job)
    mock_k8s.configure_batch_stage_job.side_effect = [
        k8sclient.ApiException(error_message),
        mock_job,
    ]
    expected_result = [
        k8sclient.V1EnvVar(name=FAILURE_EXCEPTION_K8S_ENV_VAR, value=error_message)
    ]
    mock_k8s.create_k8s_environment_variables.return_value = expected_result
    mock_k8s.configure_env_vars_from_secrets.return_value = []

    try:
        run_workflow("foo_bar_foo_993", project_repo_location, config=config)
    except BodyworkWorkflowExecutionError:
        pass

    mock_k8s.configure_batch_stage_job.assert_called_with(
        ANY,
        "on_fail_stage",
        ANY,
        ANY,
        ANY,
        retries=ANY,
        container_env_vars=expected_result,
        image=ANY,
        cpu_request=ANY,
        memory_request=ANY,
    )


@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.k8s")
def test_failure_stage_does_not_run_for_docker_image_exception(
    mock_k8s: MagicMock,
    mock_session: MagicMock,
    mock_git_download: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)
    mock_session().get.return_value = requests.Response().status_code = 401

    try:
        run_workflow("foo_bar_foo_993", project_repo_location, config=config)
    except BodyworkWorkflowExecutionError:
        pass

    mock_k8s.configure_batch_stage_job.assert_not_called()


@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.k8s")
def test_failure_stage_does_not_run_for_namespace_exception(
    mock_k8s: MagicMock, mock_git_download: MagicMock, project_repo_location: Path
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)
    mock_k8s.namespace_exists.return_value = False
    try:
        run_workflow("foo_bar_foo_993", project_repo_location, config=config)
    except BodyworkWorkflowExecutionError:
        pass

    mock_k8s.configure_batch_stage_job.assert_not_called()


@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.k8s")
def test_failure_stage_does_not_run_for_git_exception(
    mock_k8s: MagicMock, mock_git_download: MagicMock, project_repo_location: Path
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)
    mock_git_download.side_effect = BodyworkGitError("Test Exception")

    try:
        run_workflow("foo_bar_foo_993", project_repo_location, config=config)
    except BodyworkWorkflowExecutionError:
        pass

    mock_k8s.configure_batch_stage_job.assert_not_called()


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_failure_of_failure_stage_is_recorded_in_exception(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_requests: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)
    config.project.run_on_failure = "on_fail_stage"

    error_message = "The run-on-failure stage experienced an error"
    mock_k8s.configure_batch_stage_job.side_effect = [
        k8sclient.ApiException("Original Error"),
        k8sclient.ApiException(reason=error_message),
    ]
    mock_k8s.configure_env_vars_from_secrets.return_value = []

    with raises(BodyworkWorkflowExecutionError, match=f"{error_message}"):
        run_workflow("foo_bar_foo_993", project_repo_location, config=config)


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_run_workflow_pings_usage_stats_server(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_session: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)
    config.project.usage_stats = True

    run_workflow("foo_bar_foo_993", project_repo_location, config=config)

    mock_session().get.assert_called_with(
        USAGE_STATS_SERVER_URL, params={"type": "workflow"}
    )


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_usage_stats_opt_out_does_not_ping_usage_stats_server(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_session: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")

    run_workflow(
        "foo_bar_foo_993",
        project_repo_location,
        config=BodyworkConfig(config_path),
    )

    mock_session().get.assert_called_once()


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_namespace_is_not_deleted_if_there_are_service_stages(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_requests: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/{PROJECT_CONFIG_FILENAME}")
    config = BodyworkConfig(config_path)

    try:
        run_workflow("foo_bar_foo_993", project_repo_location, config=config)
    except BodyworkWorkflowExecutionError:
        pass

    mock_k8s.delete_namespace.assert_not_called()


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_namespace_is_deleted_if_only_batch_stages(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_requests: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork_batch_stage.yaml")
    config = BodyworkConfig(config_path)

    try:
        run_workflow("foo_bar_foo_993", project_repo_location, config=config)
    except BodyworkWorkflowExecutionError:
        pass

    mock_k8s.delete_namespace.assert_called()


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_old_deployments_are_cleaned_up(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_session: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
    test_service_stage_deployment: Dict[str, Any],
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)

    mock_git_hash.return_value = test_service_stage_deployment[
        "bodywork-test-project--serve-v2"
    ]["git_commit_hash"]
    mock_k8s.list_service_stage_deployments.return_value = test_service_stage_deployment

    run_workflow("project_repo_url", config=config)

    mock_k8s.delete_deployment.assert_called_once_with(
        "bodywork-test-project", "bodywork-test-project--serve-v1"
    )


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_cannot_deploy_different_project_repo_to_same_namespace(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_session: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
    test_service_stage_deployment: Dict[str, Any],
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)

    mock_k8s.list_service_stage_deployments.return_value = test_service_stage_deployment

    with raises(
        BodyworkWorkflowExecutionError,
        match=r"A project with the same name \(or namespace\): bodywork-test-project",
    ):
        run_workflow("https://my_new_project", config=config)
