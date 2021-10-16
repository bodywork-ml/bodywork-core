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
Test the Bodywork CLI.
"""
import urllib3
from pathlib import Path
from re import findall
from subprocess import run, CalledProcessError
from typing import Iterable
from unittest.mock import patch, MagicMock

import kubernetes
from pytest import raises
from _pytest.capture import CaptureFixture

from bodywork.cli.cli import _configure_cluster, handle_k8s_exceptions
from bodywork.constants import BODYWORK_DEPLOYMENT_JOBS_NAMESPACE


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
    assert "no config file found" in process_two.stdout

    config_file_path = project_repo_location / "bodywork_empty.yaml"
    process_three = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_three.returncode == 1
    assert "cannot parse YAML" in process_three.stdout

    config_file_path = project_repo_location / "bodywork_missing_sections.yaml"
    process_four = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_four.returncode == 1
    assert "missing sections: version, project, stages, logging" in process_four.stdout

    config_file_path = project_repo_location / "bodywork_bad_stages_section.yaml"
    process_five = run(
        ["bodywork", "validate", "--file", config_file_path],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_five.returncode == 1
    assert "Missing or invalid parameters" in process_five.stdout
    assert "* stages._" in process_five.stdout


def test_version_returns_version():
    with open("VERSION") as file:
        expected_version = findall("[0-9].[0.9].[0.9]", file.read())
    process = run(["bodywork", "version"], capture_output=True, encoding="utf-8")
    actual_version = findall("[0-9].[0.9].[0.9]", process.stdout)
    if expected_version and actual_version:
        assert actual_version[0] == expected_version[0]
    else:
        assert False


@patch("bodywork.cli.cli.setup_namespace_with_service_accounts_and_roles")
def test_configure_cluster_configures_cluster(mock_setup: MagicMock):
    try:
        _configure_cluster()
        assert False
    except SystemExit:
        mock_setup.assert_called_once_with(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE)


def test_stage_command_successful_has_zero_exit_code(
    setup_bodywork_test_project: Iterable[bool], project_repo_connection_string: str
):
    try:
        run(
            [
                "bodywork",
                "stage",
                project_repo_connection_string,
                "master",
                "stage_1",
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


def test_get_deployments_options():
    pass


def test_delete_deployments_options():
    pass


def test_create_cronjob_options():
    pass


def test_get_cronjob_options():
    pass


def test_create_secrets_options():
    process_one = run(
        [
            "bodywork",
            "create",
            "secret",
            "pytest-credentials",
            "--group=bodywork-dev",
            "--data",
            "FOO",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_one.returncode != 0
    assert "Could not parse secret data" in process_one.stdout


def test_get_secrets_options():
    pass


def test_update_secrets_options():
    pass
