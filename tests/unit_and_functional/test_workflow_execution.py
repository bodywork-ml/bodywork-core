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
Test Bodywork workflow execution.
"""
from pathlib import Path
from unittest.mock import ANY, MagicMock, Mock, patch
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
    SSH_PRIVATE_KEY_ENV_VAR,
    SSH_SECRET_NAME,
    TIMEOUT_GRACE_SECONDS,
)
from bodywork.exceptions import (
    BodyworkWorkflowExecutionError,
    BodyworkDockerImageError,
    BodyworkGitError,
)
from bodywork.workflow_execution import (
    _compute_optimal_deployment_timeout,
    _compute_optimal_job_timeout,
    _print_logs_to_stdout,
    image_exists_on_dockerhub,
    parse_dockerhub_image_string,
    run_workflow,)
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
        match="Invalid Docker image specified: bodyworkml",
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


def test_compute_optimal_job_timeouts():
    stage_a = Mock()
    stage_a.retries = 1
    stage_a.max_completion_time = 60

    stage_b = Mock()
    stage_b.retries = 3
    stage_b.max_completion_time = 30

    timeout = _compute_optimal_job_timeout([stage_a, stage_b])
    assert timeout == 3 * 30 + TIMEOUT_GRACE_SECONDS

    stage_b.retries = 0
    timeout = _compute_optimal_job_timeout([stage_a, stage_b])
    assert timeout == 1 * 60 + TIMEOUT_GRACE_SECONDS


@patch("bodywork.workflow_execution.k8s")
def test_compute_optimal_deployment_timeouts(mock_k8s: MagicMock):
    stage_a = Mock()
    stage_a.replicas = 2
    stage_a.max_startup_time = 60

    stage_b = Mock()
    stage_b.replicas = 3
    stage_b.max_startup_time = 45

    mock_k8s.is_existing_deployment.side_effect = [False, False]
    timeout = _compute_optimal_deployment_timeout("the-namespace", [stage_a, stage_b])
    assert timeout == 2 * 60 + TIMEOUT_GRACE_SECONDS

    mock_k8s.is_existing_deployment.side_effect = [False, True]
    timeout = _compute_optimal_deployment_timeout("the-namespace", [stage_a, stage_b])
    assert timeout == 2 * 2 * 45 + TIMEOUT_GRACE_SECONDS


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
        startup_time_seconds=ANY,
    )
    mock_k8s.configure_batch_stage_job.assert_called_with(
        ANY,
        ANY,
        ANY,
        ANY,
        retries=ANY,
        timeout=ANY,
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
    config.pipeline.run_on_failure = "on_fail_stage"

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
        retries=ANY,
        timeout=ANY,
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
    config.pipeline.run_on_failure = "on_fail_stage"

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
    config.pipeline.usage_stats = True

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
    service_stage_deployment_list: Dict[str, Dict[str, Any]],
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)

    mock_git_hash.return_value = service_stage_deployment_list[
        "bodywork-test-project/serve-v2"
    ]["git_commit_hash"]
    mock_k8s.list_service_stage_deployments.return_value = service_stage_deployment_list

    run_workflow("project_repo_url", config=config)

    mock_k8s.delete_deployment.assert_called_once_with(
        "bodywork-test-project", "serve-v1"
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
    service_stage_deployment_list: Dict[str, Dict[str, Any]],
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)

    mock_k8s.list_service_stage_deployments.return_value = service_stage_deployment_list

    with raises(
        BodyworkWorkflowExecutionError,
        match=r"A project with the same name \(or namespace\): bodywork-test-project",
    ):
        run_workflow("https://my_new_project", config=config)


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_run_workflow_adds_ssh_key_env_var_from_file(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_session: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)

    expected_result = k8sclient.V1EnvVar(
        name=SSH_PRIVATE_KEY_ENV_VAR,
        value_from=k8sclient.V1EnvVarSource(
            secret_key_ref=k8sclient.V1SecretKeySelector(
                key=SSH_PRIVATE_KEY_ENV_VAR, name=SSH_SECRET_NAME, optional=False
            )
        ),
    )

    mock_k8s.create_k8s_environment_variables.return_value = []
    mock_k8s.configure_env_vars_from_secrets.return_value = []
    mock_k8s.create_secret_env_variable.return_value = expected_result

    run_workflow("https://my_new_project", config=config, ssh_key_path="mykey")

    mock_k8s.create_ssh_key_secret_from_file.assert_called_with("test", Path("mykey"))
    mock_k8s.configure_batch_stage_job.assert_called_with(
        ANY,
        ANY,
        ANY,
        ANY,
        retries=ANY,
        timeout=ANY,
        container_env_vars=[expected_result],
        image=ANY,
        cpu_request=ANY,
        memory_request=ANY,
    )


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_workflow_adds_ssh_secret_if_default_exists(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_session: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/{PROJECT_CONFIG_FILENAME}")
    config = BodyworkConfig(config_path)
    config.pipeline.secrets_group = None

    expected_result = k8sclient.V1EnvVar(
        name=SSH_PRIVATE_KEY_ENV_VAR,
        value_from=k8sclient.V1EnvVarSource(
            secret_key_ref=k8sclient.V1SecretKeySelector(
                key=SSH_PRIVATE_KEY_ENV_VAR, name=SSH_SECRET_NAME, optional=False
            )
        ),
    )

    mock_k8s.create_k8s_environment_variables.return_value = []
    mock_k8s.configure_env_vars_from_secrets.return_value = []
    mock_k8s.create_secret_env_variable.return_value = expected_result

    run_workflow("git@github.com:my_new_project", config=config)

    mock_k8s.configure_batch_stage_job.assert_called_with(
        ANY,
        ANY,
        ANY,
        ANY,
        retries=ANY,
        timeout=ANY,
        container_env_vars=[expected_result],
        image=ANY,
        cpu_request=ANY,
        memory_request=ANY,
    )


@patch("bodywork.workflow_execution.rmtree")
@patch("bodywork.workflow_execution.requests.Session")
@patch("bodywork.workflow_execution.download_project_code_from_repo")
@patch("bodywork.workflow_execution.get_git_commit_hash")
@patch("bodywork.workflow_execution.k8s")
def test_workflow_adds_ssh_secret_if_exists_in_group(
    mock_k8s: MagicMock,
    mock_git_hash: MagicMock,
    mock_git_download: MagicMock,
    mock_session: MagicMock,
    mock_rmtree: MagicMock,
    project_repo_location: Path,
):
    config_path = Path(f"{project_repo_location}/bodywork.yaml")
    config = BodyworkConfig(config_path)

    expected_result = k8sclient.V1EnvVar(
        name=SSH_PRIVATE_KEY_ENV_VAR,
        value_from=k8sclient.V1EnvVarSource(
            secret_key_ref=k8sclient.V1SecretKeySelector(
                key=SSH_PRIVATE_KEY_ENV_VAR, name=SSH_SECRET_NAME, optional=False
            )
        ),
    )

    mock_k8s.create_k8s_environment_variables.return_value = []
    mock_k8s.configure_env_vars_from_secrets.return_value = []
    mock_k8s.create_secret_env_variable.return_value = expected_result

    run_workflow("git@github.com:my_new_project", config=config)

    mock_k8s.configure_batch_stage_job.assert_called_with(
        ANY,
        ANY,
        ANY,
        ANY,
        retries=ANY,
        timeout=ANY,
        container_env_vars=[expected_result],
        image=ANY,
        cpu_request=ANY,
        memory_request=ANY,
    )
