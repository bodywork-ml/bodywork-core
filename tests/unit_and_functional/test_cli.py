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
from argparse import Namespace
from pathlib import Path
from subprocess import run, CalledProcessError
from typing import Iterable
from unittest.mock import MagicMock, patch

import kubernetes
from pytest import raises
from _pytest.capture import CaptureFixture

from bodywork.cli.cli import deployment, handle_k8s_exceptions
from bodywork.constants import BODYWORK_NAMESPACE


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


def test_stage_subcommand_exists():
    process = run(["bodywork", "stage", "-h"], encoding="utf-8", capture_output=True)
    expected_output = "bodywork stage [-h]"
    assert process.stdout.find(expected_output) != -1


def test_stage_command_receives_correct_args():
    process = run(
        ["bodywork", "stage", "http://my.project.com", "master", "train"],
        encoding="utf-8",
        capture_output=True,
    )
    expected_output = "Attempting to run stage"
    assert expected_output in process.stdout


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


def test_stage_command_unsuccessful_raises_exception():
    with raises(CalledProcessError):
        run(["bodywork", "stage", "http://bad.repo", "master", "train"], check=True)


def test_workflow_subcommand_exists():
    process = run(["bodywork", "workflow", "-h"], encoding="utf-8", capture_output=True)
    expected_output = (
        "usage: bodywork workflow [-h] [--bodywork-docker-image"
        "BODYWORK_DOCKER_IMAGE] namespace git_url"
        " git_branch"
    )
    assert process.stdout.find(expected_output) != 0


def test_secrets_subcommand_exists():
    process = run(["bodywork", "secret", "-h"], encoding="utf-8", capture_output=True)
    expected_output = "bodywork secret [-h]"
    assert process.stdout.find(expected_output) != -1


def test_cli_secret_handler_error_handling():
    process_one = run(
        [
            "bodywork",
            "secret",
            "create",
            "--group=bodywork-dev",
            "--data",
            "USERNAME=alex",
            "PASSWORD=alex123",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify the name of the secret" in process_one.stdout

    process_two = run(
        [
            "bodywork",
            "secret",
            "delete",
            "--group=bodywork-dev",
            "--data",
            "USERNAME=alex",
            "PASSWORD=alex123",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify the name of the secret" in process_two.stdout

    process_three = run(
        [
            "bodywork",
            "secret",
            "create",
            "--group=bodywork-dev",
            "--name=pytest-credentials",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify keys and values" in process_three.stdout

    process_four = run(
        [
            "bodywork",
            "secret",
            "create",
            "--group=bodywork-dev",
            "--name=pytest-credentials",
            "--data",
            "FOO",
            "bar",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Could not parse secret data" in process_four.stdout

    process_five = run(
        [
            "bodywork",
            "secret",
            "create",
            "--name=pytest-credentials",
            "--data",
            "USERNAME=alex",
            "PASSWORD=alex123",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        "Please specify the secret group the secret belongs to" in process_five.stdout
    )


def test_deployment_subcommand_exists():
    process = run(
        ["bodywork", "deployment", "-h"], encoding="utf-8", capture_output=True
    )
    expected_output = "usage: bodywork deployment [-h]"
    assert process.stdout.find(expected_output) != -1


@patch("bodywork.cli.cli.setup_namespace_with_service_accounts_and_roles")
@patch("bodywork.cli.cli.is_namespace_available_for_bodywork")
@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.run_workflow")
@patch("sys.exit")
def test_deployment_create_configures_cluster_if_required(
    mock_sys_exit: MagicMock,
    mock_workflow_cli_handler: MagicMock,
    mock_load_config: MagicMock,
    mock_namespace: MagicMock,
    mock_configure_cluster: MagicMock,
    capsys: CaptureFixture,
):
    args = Namespace(
        command="create",
        name="foo2",
        retries=0,
        git_url="foo3",
        git_branch="foo4",
        async_workflow=None,
        namespace=None,
        service=None,
        bodywork_docker_image=None,
        ssh_key_path=None,
        group=None,
    )
    mock_namespace.return_value = False
    deployment(args)

    stdout = capsys.readouterr().out
    msg = (
        "Cluster has not been configured for Bodywork - "
        "running 'bodywork configure-cluster'."
    )
    assert msg in stdout
    mock_configure_cluster.assert_called_once_with(
        BODYWORK_NAMESPACE
    )


@patch("bodywork.cli.cli.is_namespace_available_for_bodywork")
@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.run_workflow")
@patch("sys.exit")
def test_deployment_run_locally_calls_run_workflow_handler(
    mock_sys_exit: MagicMock,
    mock_workflow_cli_handler: MagicMock,
    mock_load_config: MagicMock,
    mock_namespace: MagicMock,
    capsys: CaptureFixture,
):
    args = Namespace(
        command="create",
        name="foo2",
        retries=0,
        git_url="foo3",
        git_branch="foo4",
        async_workflow=None,
        namespace=None,
        service=None,
        bodywork_docker_image=None,
        ssh_key_path=None,
        group=None,
    )
    mock_namespace.return_value = True
    deployment(args)

    stdout = capsys.readouterr().out
    assert "Using local workflow controller - retries inactive" in stdout
    mock_workflow_cli_handler.assert_called_once_with("foo3", "foo4", docker_image_override=None, ssh_key_path=None)


def test_cli_deployment_handler_error_handling():
    process_one = run(
        ["bodywork", "deployment", "logs"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify --name for the deployment job" in process_one.stdout
    assert process_one.returncode == 1

    process_two = run(
        [
            "bodywork",
            "deployment",
            "create",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify Git repo URL" in process_two.stdout
    assert process_two.returncode == 1


@patch("bodywork.cli.cli.is_namespace_available_for_bodywork")
@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.sys")
@patch("bodywork.cli.cli.create_workflow_job")
def test_cli_deployment_create_async(
    mock_create_workflow: MagicMock,
    mock_sys: MagicMock,
    mock_load_config: MagicMock,
    mock_namespace: MagicMock,
):
    args = Namespace(
        command="create",
        name="test_cli",
        async_workflow=True,
        git_url="http://Test",
        git_branch="master",
        retries=2,
        namespace=None,
        service=None,
        bodywork_docker_image="bodywork-ml:myimage",
        ssh_key_path=None,
        group=None,
    )
    mock_namespace.return_value = True
    deployment(args)

    mock_create_workflow.assert_called_with(
        BODYWORK_NAMESPACE,
        args.name,
        args.git_url,
        args.git_branch,
        args.retries,
        args.bodywork_docker_image,
        None,
        None,
    )


@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.sys")
@patch("bodywork.cli.cli.delete_deployment")
def test_cli_deployment_delete(
    mock_deployments: MagicMock, mock_sys: MagicMock, mock_load_config: MagicMock
):
    args = Namespace(
        command="delete",
        name="mydeployment",
        async_workflow=None,
        git_url=None,
        git_branch="master",
        retries=2,
        namespace=None,
        service=None,
        bodywork_docker_image=None,
        ssh_key_path=None,
        group=None,
    )

    deployment(args)

    mock_deployments.assert_called_with(args.name)


@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.sys")
@patch("bodywork.cli.cli.display_workflow_job_logs")
def test_cli_deployment_logs(
    mock_workflow_job: MagicMock, mock_sys: MagicMock, mock_load_config
):
    args = Namespace(
        command="logs",
        name="mydeployment",
        async_workflow=None,
        git_url=None,
        git_branch="master",
        retries=2,
        namespace=None,
        service=None,
        bodywork_docker_image=None,
        ssh_key_path=None,
        group=None,
    )

    deployment(args)

    mock_workflow_job.assert_called_with(BODYWORK_NAMESPACE, args.name)


@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.sys")
@patch("bodywork.cli.cli.delete_workflow_job")
def test_cli_deployment_delete_job(
    mock_workflow_job: MagicMock, mock_sys: MagicMock, mock_load_config
):
    args = Namespace(
        command="delete_job",
        name="mydeployment",
        async_workflow=None,
        git_url=None,
        git_branch="master",
        retries=2,
        namespace=None,
        service=None,
        bodywork_docker_image=None,
        ssh_key_path=None,
        group=None,
    )

    deployment(args)

    mock_workflow_job.assert_called_with(BODYWORK_NAMESPACE, args.name)


@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.sys")
@patch("bodywork.cli.cli.display_workflow_job_history")
def test_cli_deployment_job_history(
    mock_workflow_job: MagicMock, mock_sys: MagicMock, mock_load_config
):
    args = Namespace(
        command="job_history",
        name="mydeployment",
        async_workflow=None,
        git_url=None,
        git_branch="master",
        retries=2,
        namespace=None,
        service=None,
        bodywork_docker_image=None,
        ssh_key_path=None,
        group=None,
    )

    deployment(args)

    mock_workflow_job.assert_called_with(BODYWORK_NAMESPACE, args.name)


@patch("bodywork.cli.cli.load_kubernetes_config")
@patch("bodywork.cli.cli.sys")
@patch("bodywork.cli.cli.display_deployments")
def test_cli_deployment_display(
    mock_display_deployments: MagicMock, mock_sys: MagicMock, mock_load_config
):
    args = Namespace(
        command="display",
        name="mydeployment",
        async_workflow=None,
        git_url=None,
        git_branch="master",
        retries=2,
        namespace=None,
        service=None,
        bodywork_docker_image=None,
        ssh_key_path=None,
        group=None,
    )

    deployment(args)

    mock_display_deployments.assert_called_with(args.namespace, args.name, args.service)


def test_cronjobs_subcommand_exists():
    process = run(["bodywork", "cronjob", "-h"], encoding="utf-8", capture_output=True)
    expected_output = "usage: bodywork cronjob [-h]"
    assert process.stdout.find(expected_output) != -1


def test_cli_cronjob_handler_error_handling():
    process_one = run(
        ["bodywork", "cronjob", "create"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify --name for the cronjob" in process_one.stdout
    assert process_one.returncode == 1

    process_two = run(
        ["bodywork", "cronjob", "delete"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify --name for the cronjob" in process_two.stdout
    assert process_two.returncode == 1

    process_three = run(
        ["bodywork", "cronjob", "history"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify --name for the cronjob" in process_three.stdout
    assert process_three.returncode == 1

    process_three = run(
        ["bodywork", "cronjob", "logs"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify --name for the cronjob" in process_three.stdout
    assert process_three.returncode == 1

    process_five = run(
        [
            "bodywork",
            "cronjob",
            "create",
            "--name=the-cronjob",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify schedule for the cronjob" in process_five.stdout
    assert process_five.returncode == 1

    process_six = run(
        [
            "bodywork",
            "cronjob",
            "create",
            "--name=the-cronjob",
            "--schedule=0 * * * *",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify Git repo URL" in process_six.stdout
    assert process_six.returncode == 1


def test_cronjob_update_error_handling():
    process_one = run(
        [
            "bodywork",
            "cronjob",
            "update",
            "--name=the-cronjob",
            "--git-url=https://test",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Please specify both --git-url and --git-branch." in process_one.stdout
    assert process_one.returncode == 1


def test_setup_namespace_subcommand_exists():
    process = run(
        ["bodywork", "setup-namespace", "-h"], encoding="utf-8", capture_output=True
    )
    expected_output = "usage: bodywork setup-namespace [-h] namespace"
    assert process.stdout.find(expected_output) != -1


def test_debug_subcommand_exists():
    process = run(["bodywork", "debug", "-h"], encoding="utf-8", capture_output=True)
    expected_output = "usage: bodywork debug [-h] seconds"
    assert process.stdout.find(expected_output) != -1


def test_debug_subcommand_sleeps():
    process = run(
        ["bodywork", "debug", "1"],
        encoding="utf-8",
        capture_output=True,
    )
    expected_output = "sleeping for 1s"
    assert process.stdout.find(expected_output) != -1
    assert process.returncode == 0


def test_configure_cluster_subcommand_exists():
    process = run(
        ["bodywork", "configure-cluster", "-h"], encoding="utf-8", capture_output=True
    )
    expected_output = "bodywork configure-cluster [-h]"
    assert process.stdout.find(expected_output) != -1


def test_graceful_exit_when_no_command_specified():
    process = run(
        ["bodywork"],
        encoding="utf-8",
        capture_output=True,
    )
    assert process.returncode == 0


def test_validate_subcommand(project_repo_location: Path):
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
