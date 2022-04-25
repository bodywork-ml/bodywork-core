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
Test the Bodywork CLI.
"""
import urllib3
from pathlib import Path
from re import match
from subprocess import run, CalledProcessError
from typing import Iterable
from unittest.mock import patch, MagicMock

import kubernetes
from _pytest.capture import CaptureFixture

from bodywork.cli.cli import (
    k8s_auth,
    handle_k8s_exceptions,
    _configure_cluster,
    _create_deployment,
    _get_deployment,
    _update_deployment,
    _delete_deployment,
    _create_secret,
    _get_secret,
    _update_secret,
    _delete_secret,
    _create_cronjob,
    _get_cronjob,
    _update_cronjob,
    _delete_cronjob,
)
from bodywork.constants import BODYWORK_NAMESPACE


@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.print_warn")
def test_k8s_auth(mock_print_warn: MagicMock, mock_load_k8s_config: MagicMock):
    k8s_auth(lambda e: None)
    mock_load_k8s_config.assert_called_once()

    mock_load_k8s_config.side_effect = Exception()
    k8s_auth(lambda e: None)
    mock_print_warn.assert_called_once()


def test_handle_k8s_exceptions_decorator_handles_k8s_api_exceptions(
    capsys: CaptureFixture,
):
    @handle_k8s_exceptions
    def outer_func():
        def inner_func():
            raise kubernetes.client.rest.ApiException()

        return inner_func()

    outer_func()
    captured_stdout = capsys.readouterr().out
    assert "Kubernetes API error returned" in captured_stdout


def test_handle_k8s_exceptions_decorator_handles_max_retry_error(
    capsys: CaptureFixture,
):
    @handle_k8s_exceptions
    def outer_func():
        def inner_func():
            raise urllib3.exceptions.MaxRetryError("pool", "url")

        return inner_func()

    outer_func()
    captured_stdout = capsys.readouterr().out
    assert "Failed to connect to the Kubernetes API" in captured_stdout


def test_handle_k8s_exceptions_decorator_handles_k8s_config_exceptions(
    capsys: CaptureFixture,
):
    @handle_k8s_exceptions
    def func():
        raise kubernetes.config.ConfigException()

    func()
    captured_stdout = capsys.readouterr().out
    assert "Cannot load authentication credentials from kubeconfig" in captured_stdout


def test_cli_commands_exist():
    validate = run(
        ["bodywork", "validate", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    assert validate.returncode == 0

    version = run(
        ["bodywork", "version", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    assert version.returncode == 0

    stage = run(
        ["bodywork", "stage", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    assert stage.returncode == 0

    debug = run(
        ["bodywork", "debug", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    assert debug.returncode == 0

    create_deployment = run(
        ["bodywork", "create", "deployment", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    get_deployment = run(
        ["bodywork", "get", "deployment", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    update_deployment = run(
        ["bodywork", "update", "deployment", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    delete_deployment = run(
        ["bodywork", "delete", "deployment", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    assert create_deployment.returncode == 0
    assert get_deployment.returncode == 0
    assert update_deployment.returncode == 0
    assert delete_deployment.returncode == 0

    create_cronjob = run(
        ["bodywork", "create", "cronjob", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    get_cronjob = run(
        ["bodywork", "get", "cronjob", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    update_cronjob = run(
        ["bodywork", "update", "cronjob", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    delete_cronjob = run(
        ["bodywork", "delete", "cronjob", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    assert create_cronjob.returncode == 0
    assert get_cronjob.returncode == 0
    assert update_cronjob.returncode == 0
    assert delete_cronjob.returncode == 0

    create_secret = run(
        ["bodywork", "create", "secret", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    get_secret = run(
        ["bodywork", "get", "secret", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    update_secret = run(
        ["bodywork", "update", "secret", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    delete_secret = run(
        ["bodywork", "delete", "secret", "--help"],
        encoding="utf-8",
        capture_output=True,
    )
    assert create_secret.returncode == 0
    assert get_secret.returncode == 0
    assert update_secret.returncode == 0
    assert delete_secret.returncode == 0


def test_validate(project_repo_location: Path):
    config_file_path = project_repo_location / "bodywork.yaml"
    process_one = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_one.returncode == 0

    config_file_path = project_repo_location / "does_not_exist.yaml"
    process_two = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_two.returncode == 1
    assert "No config file found" in process_two.stdout

    config_file_path = project_repo_location / "bodywork_empty.yaml"
    process_three = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_three.returncode == 1
    assert "Cannot parse YAML" in process_three.stdout

    config_file_path = project_repo_location / "bodywork_missing_sections.yaml"
    process_four = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_four.returncode == 1
    assert "missing sections: version, pipeline, stages, logging" in process_four.stdout

    config_file_path = project_repo_location / "bodywork_bad_stages_section.yaml"
    process_five = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_five.returncode == 1
    assert "Missing or invalid parameters" in process_five.stdout
    assert "* stages._" in process_five.stdout


def test_version_returns_valid_pkg_version():
    pkg_version_regex = r"\d.\d.\d($|\\n|a\d+|b\d+||rc\d+|.dev\d+|.post\d+)"
    with open("VERSION") as file:
        expected_version = match(pkg_version_regex, file.read())
    process = run(["bodywork", "version"], capture_output=True, encoding="utf-8")
    actual_version = match(pkg_version_regex, process.stdout)
    if expected_version and actual_version:
        assert actual_version[0] == expected_version[0]
    else:
        if process.stderr:
            print(process.stderr)
        assert False


@patch("bodywork.cli.cli.setup_namespace_with_service_accounts_and_roles")
@patch("bodywork.cli.cli.sys")
def test_configure_cluster_configures_cluster(
    mock_sys: MagicMock, mock_setup: MagicMock
):
    _configure_cluster()
    mock_setup.assert_called_once_with(BODYWORK_NAMESPACE)


def test_stage_command_successful_has_zero_exit_code(
    setup_bodywork_test_project: Iterable[bool], project_repo_connection_string: str
):
    try:
        run(
            [
                "bodywork",
                "stage",
                project_repo_connection_string,
                "stage_1",
                "--branch",
                "master",
            ],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        assert True
    except CalledProcessError as e:
        print(f"Test Failed - {e.stderr}")
        assert False


def test_stage_command_unsuccessful_returns_non_zero_exit_code():
    process = run(["bodywork", "stage", "http://bad.repo", "master", "train"])
    assert process.returncode != 0


def test_debug_subcommand_sleeps():
    process = run(
        ["bodywork", "debug", "1"],
        encoding="utf-8",
        capture_output=True,
    )
    expected_output = "sleeping for 1s"
    assert process.stdout.find(expected_output) != -1
    assert process.returncode == 0


@patch("bodywork.cli.cli.is_namespace_available_for_bodywork")
@patch("bodywork.cli.cli.setup_namespace_with_service_accounts_and_roles")
@patch("bodywork.cli.cli.run_workflow")
@patch("bodywork.cli.cli.create_workflow_job")
@patch("bodywork.cli.cli.sys")
def test_create_deployments(
    mock_sys: MagicMock,
    mock_create_workflow_job: MagicMock,
    mock_run_workflow: MagicMock,
    mock_setup_namespace_with_service_accounts_and_roles: MagicMock,
    mock_is_namespace_available_for_bodywork: MagicMock,
):
    mock_is_namespace_available_for_bodywork.return_value = False
    _create_deployment("git-url", "git-branch", False)
    mock_setup_namespace_with_service_accounts_and_roles.assert_called_once()
    mock_run_workflow.assert_called_once()
    mock_create_workflow_job.assert_not_called()

    mock_setup_namespace_with_service_accounts_and_roles.reset_mock()
    mock_run_workflow.reset_mock()
    mock_is_namespace_available_for_bodywork.return_value = True
    _create_deployment("git-url", "git-branch", False)
    mock_setup_namespace_with_service_accounts_and_roles.assert_not_called()
    mock_run_workflow.assert_called_once()
    mock_create_workflow_job.assert_not_called()

    mock_setup_namespace_with_service_accounts_and_roles.reset_mock()
    mock_run_workflow.reset_mock()
    mock_is_namespace_available_for_bodywork.return_value = True
    _create_deployment("git-url", "git-branch", True)
    mock_setup_namespace_with_service_accounts_and_roles.assert_not_called()
    mock_run_workflow.assert_not_called()
    mock_create_workflow_job.assert_called_once()


@patch("bodywork.cli.cli.display_workflow_job_history")
@patch("bodywork.cli.cli.display_workflow_job_logs")
@patch("bodywork.cli.cli.display_deployments")
@patch("bodywork.cli.cli.print_warn")
@patch("bodywork.cli.cli.sys")
def test_get_deployments(
    mock_sys: MagicMock,
    mock_print_warn: MagicMock,
    mock_display_deployment: MagicMock,
    mock_display_workflow_job_logs: MagicMock,
    mock_display_workflow_job_history: MagicMock,
):
    _get_deployment(asynchronous=True, logs="")
    mock_display_workflow_job_history.assert_called_once()

    _get_deployment(asynchronous=True, logs="name-of-async-workflow-job")
    mock_display_workflow_job_logs.assert_called_once()

    _get_deployment(asynchronous=False, logs="")
    mock_display_deployment.assert_called_once()


@patch("bodywork.cli.cli.is_namespace_available_for_bodywork")
@patch("bodywork.cli.cli.setup_namespace_with_service_accounts_and_roles")
@patch("bodywork.cli.cli.run_workflow")
@patch("bodywork.cli.cli.create_workflow_job")
@patch("bodywork.cli.cli.sys")
def test_update_deployments(
    mock_sys: MagicMock,
    mock_create_workflow_job: MagicMock,
    mock_run_workflow: MagicMock,
    mock_setup_namespace_with_service_accounts_and_roles: MagicMock,
    mock_is_namespace_available_for_bodywork: MagicMock,
):
    mock_is_namespace_available_for_bodywork.return_value = False
    _update_deployment("git-url", "git-branch", False)
    mock_setup_namespace_with_service_accounts_and_roles.assert_called_once()
    mock_run_workflow.assert_called_once()
    mock_create_workflow_job.assert_not_called()

    mock_setup_namespace_with_service_accounts_and_roles.reset_mock()
    mock_run_workflow.reset_mock()
    mock_is_namespace_available_for_bodywork.return_value = True
    _update_deployment("git-url", "git-branch", False)
    mock_setup_namespace_with_service_accounts_and_roles.assert_not_called()
    mock_run_workflow.assert_called_once()
    mock_create_workflow_job.assert_not_called()

    mock_setup_namespace_with_service_accounts_and_roles.reset_mock()
    mock_run_workflow.reset_mock()
    mock_is_namespace_available_for_bodywork.return_value = True
    _update_deployment("git-url", "git-branch", True)
    mock_setup_namespace_with_service_accounts_and_roles.assert_not_called()
    mock_run_workflow.assert_not_called()
    mock_create_workflow_job.assert_called_once()


@patch("bodywork.cli.cli.delete_workflow_job")
@patch("bodywork.cli.cli.delete_deployment")
@patch("bodywork.cli.cli.sys")
def test_delete_deployments(
    mock_sys: MagicMock,
    mock_delete_deployments: MagicMock,
    mock_delete_workflow_job: MagicMock,
):
    _delete_deployment("foo", asynchronous=False)
    mock_delete_deployments.assert_called_once()

    _delete_deployment("foo", asynchronous=True)
    mock_delete_workflow_job.assert_called_once()


@patch("bodywork.cli.cli.create_workflow_cronjob")
@patch("bodywork.cli.cli.sys")
def test_create_cronjob(mock_sys: MagicMock, mock_create_workflow_cronjob: MagicMock):
    _create_cronjob("git-repo", "git-url", "0 * * * *", "nightly")
    mock_create_workflow_cronjob.assert_called_once()


@patch("bodywork.cli.cli.print_warn")
@patch("bodywork.cli.cli.display_workflow_job_logs")
@patch("bodywork.cli.cli.display_workflow_job_history")
@patch("bodywork.cli.cli.display_cronjobs")
@patch("bodywork.cli.cli.sys")
def test_get_cronjob(
    mock_sys: MagicMock,
    mock_display_cronjobs: MagicMock,
    mock_display_workflow_job_history: MagicMock,
    mock_display_workflow_job_logs: MagicMock,
    mock_print_warn: MagicMock,
):
    _get_cronjob(name="foo", history=True, logs=False)
    mock_display_workflow_job_history.assert_called_once()

    _get_cronjob(name="foo", history=False, logs=True)
    mock_display_workflow_job_logs.assert_called_once()

    _get_cronjob(name="foo", history=True, logs=True)
    mock_print_warn.assert_called_once()

    _get_cronjob(name=None, history=False, logs=False)
    mock_display_cronjobs.assert_called_once()


@patch("bodywork.cli.cli.update_workflow_cronjob")
@patch("bodywork.cli.cli.sys")
def test_update_cronjob(mock_sys: MagicMock, mock_update_workflow_cronjob: MagicMock):
    _update_cronjob("git-repo", "git-url", "0 * * * *", "nightly")
    mock_update_workflow_cronjob.assert_called_once()


@patch("bodywork.cli.cli.delete_workflow_cronjob")
@patch("bodywork.cli.cli.sys")
def test_delete_cronjob(mock_sys: MagicMock, mock_delete_workflow_cronjob: MagicMock):
    _delete_cronjob("nightly")
    mock_delete_workflow_cronjob.assert_called_once()


@patch("bodywork.cli.cli.create_secret")
@patch("bodywork.cli.cli.print_warn")
@patch("bodywork.cli.cli.sys")
def test_create_secrets(
    mock_sys: MagicMock, mock_print_warn: MagicMock, mock_create_secret: MagicMock
):
    _create_secret("foo", "prod", ["bad-secret-data"])
    mock_print_warn.assert_called_once()

    _create_secret("foo", "prod", ["FOO=BAR"])
    mock_create_secret.assert_called_once()


@patch("bodywork.cli.cli.display_secrets")
@patch("bodywork.cli.cli.print_warn")
@patch("bodywork.cli.cli.sys")
def test_get_secrets(
    mock_sys: MagicMock, mock_print_warn: MagicMock, mock_display_secrets: MagicMock
):
    _get_secret(name="foo", group=None)
    mock_print_warn.assert_called_once()

    _get_secret()
    mock_display_secrets.assert_called_once()

    mock_display_secrets.reset_mock()
    mock_display_secrets.reset_mock()
    _get_secret(name="foo", group="prod")
    mock_display_secrets.assert_called_once()

    mock_display_secrets.reset_mock()
    _get_secret(name=None, group="prod")
    mock_display_secrets.assert_called_once()


@patch("bodywork.cli.cli.update_secret")
@patch("bodywork.cli.cli.print_warn")
@patch("bodywork.cli.cli.sys")
def test_update_secrets(
    mock_sys: MagicMock, mock_print_warn: MagicMock, mock_update_secret: MagicMock
):
    _update_secret("foo", "prod", ["bad-secret-data"])
    mock_print_warn.assert_called_once()

    _update_secret("foo", "prod", ["FOO=BAR"])
    mock_update_secret.assert_called_once()


@patch("bodywork.cli.cli.delete_secret_group")
@patch("bodywork.cli.cli.delete_secret")
@patch("bodywork.cli.cli.print_warn")
@patch("bodywork.cli.cli.sys")
def test_delete_secrets(
    mock_sys: MagicMock,
    mock_print_warn: MagicMock,
    mock_delete_secret: MagicMock,
    mock_delete_group: MagicMock,
):
    _delete_secret(name="foo", group=None)
    mock_print_warn.assert_called_once()

    mock_print_warn.reset_mock()
    _delete_secret(name=None, group=None)
    mock_print_warn.assert_called_once()

    _delete_secret(name="foo", group="prod")
    mock_delete_secret.assert_called_once()

    _delete_secret(name=None, group="test")
    mock_delete_group.assert_called_once()
