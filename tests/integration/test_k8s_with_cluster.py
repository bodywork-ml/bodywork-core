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
Test high-level k8s interaction with a k8s cluster to run stages and a
demo repo at https://github.com/bodywork-ml/bodywork-test-project.
"""
import requests
from re import findall
from shutil import rmtree
from subprocess import CalledProcessError, CompletedProcess, run
from time import sleep
from pathlib import Path

from pytest import raises, mark

from bodywork.constants import (
    SSH_DIR_NAME,
    BODYWORK_NAMESPACE,
    DEFAULT_SSH_FILE,
)
from bodywork.k8s import (
    delete_namespace,
    load_kubernetes_config,
    namespace_exists,
)


def print_completed_process_info(process: CompletedProcess) -> None:
    """Print completed prcess info to stdout to help with debugging."""
    print(f"command = {' '.join(process.args)}")
    print("stdout:")
    print(process.stdout)


@mark.usefixtures("setup_cluster")
@mark.usefixtures("add_secrets")
def test_workflow_and_service_management_end_to_end_from_cli(
    docker_image: str, ingress_load_balancer_url: str
):
    try:
        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                f"--bodywork-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )

        expected_output_1 = "deploying master branch from https://github.com/bodywork-ml/bodywork-test-project"  # noqa
        expected_output_2 = "Creating k8s namespace = bodywork-test-project"
        expected_output_3 = "Creating k8s service account = bodywork-stage"
        expected_output_4 = "Replicating k8s secrets from group = testsecrets"
        expected_output_5 = "Creating k8s job for stage = stage-1"
        expected_output_6 = "Creating k8s deployment and service for stage = stage-4"
        expected_output_7 = "Deployment successful"

        assert findall(expected_output_1, process.stdout)
        assert findall(expected_output_2, process.stdout)
        assert findall(expected_output_3, process.stdout)
        assert findall(expected_output_4, process.stdout)
        assert findall(expected_output_5, process.stdout)
        assert findall(expected_output_6, process.stdout)
        assert findall(expected_output_7, process.stdout)
        assert process.returncode == 0

        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                f"--bodywork-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0

        process = run(
            ["bodywork", "get", "deployments"],
            encoding="utf-8",
            capture_output=True,
        )

        assert "stage-3" in process.stdout
        assert "stage-4" in process.stdout
        assert process.returncode == 0

        stage_3_service_external_url = (
            f"http://{ingress_load_balancer_url}/bodywork-test-project/"
            f"/stage-3/v1/predict"
        )
        response_stage_3 = requests.get(url=stage_3_service_external_url)
        assert response_stage_3.ok
        assert response_stage_3.json()["y"] == "hello_world"

        stage_4_service_external_url = (
            f"http://{ingress_load_balancer_url}/bodywork-test-project/"
            f"/stage-4/v2/predict"
        )
        response_stage_4 = requests.get(url=stage_4_service_external_url)
        assert response_stage_4.status_code == 404

        process = run(
            [
                "bodywork",
                "delete",
                "deployment",
                "bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "deployment=bodywork-test-project deleted." in process.stdout

        assert process.returncode == 0

        sleep(5)

        process = run(
            [
                "bodywork",
                "get",
                "deployments",
                "bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "No deployments found" in process.stdout
        assert process.returncode == 0

    except Exception:
        print_completed_process_info(process)
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-project")


@mark.usefixtures("setup_cluster")
def test_services_from_previous_deployments_are_deleted():
    try:
        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/test-single-service-project.git",
                "test-two-services",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0
        assert "Deployment successful" in process.stdout

        sleep(5)

        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/test-single-service-project.git",
                "master",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0
        assert "Deployment successful" in process.stdout
        assert (
            "Removing service: stage-2 from previous deployment with git-commit-hash"
            in process.stdout
        )

        process = run(
            [
                "bodywork",
                "get",
                "deployment",
                "bodywork-test-single-service-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0
        assert "stage-1" in process.stdout
        assert "stage-2" not in process.stdout

    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-single-service-project")


@mark.usefixtures("setup_cluster")
def test_workflow_will_cleanup_jobs_and_rollback_new_deployments_that_yield_errors(
    docker_image: str,
):
    try:
        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/bodywork-rollback-deployment-test-project",  # noqa
                "master",
                f"--bodywork-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_0 = "Deleted k8s job for stage = stage-1"
        assert expected_output_0 in process.stdout
        assert process.returncode == 0

        process = run(
            [
                "bodywork",
                "update",
                "deployment",
                "https://github.com/bodywork-ml/bodywork-rollback-deployment-test-project",  # noqa
                "master",
                f"--bodywork-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_1 = "Deployments failed to roll-out successfully"
        expected_output_2 = "Rolled-back k8s deployment for stage = stage-2"
        assert expected_output_1 in process.stdout
        assert expected_output_2 in process.stdout
        assert process.returncode == 1

    except Exception:
        print_completed_process_info(process)
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-rollback-deployment-test-project")


@mark.usefixtures("setup_cluster")
def test_deploy_will_run_failure_stage_on_workflow_failure(docker_image: str):
    try:
        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/bodywork-failing-test-project",
                "master",
                f"--bodywork-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )

        expected_output_0 = "Deployment failed --> "
        expected_output_1 = "Completed k8s job for stage = on-fail-stage"
        expected_output_2 = "I have successfully been executed"
        assert expected_output_0 in process.stdout
        assert expected_output_1 in process.stdout
        assert expected_output_2 in process.stdout
        assert process.returncode == 1
    except Exception:
        print_completed_process_info(process)
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-failing-test-project")


@mark.usefixtures("setup_cluster")
def test_deployment_will_not_run_if_bodywork_docker_image_cannot_be_located():
    try:
        bad_image = "bad:bodyworkml/bodywork-core:0.0.0"
        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                f"--bodywork-image={bad_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert f"Invalid Docker image specified: {bad_image}" in process.stdout
        assert process.returncode == 1

        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                "--bodywork-image=bodyworkml/bodywork-not-an-image:latest",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert (
            "Cannot locate bodyworkml/bodywork-not-an-image:latest on DockerHub"
            in process.stdout
        )
        assert process.returncode == 1
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-project")


def test_deployment_with_ssh_github_connectivity(
    docker_image: str,
    set_github_ssh_private_key_env_var: None,
):
    try:
        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "git@github.com:bodywork-ml/test-bodywork-batch-job-project.git",
                "master",
                f"--bodywork-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_1 = "deploying master branch from git@github.com:bodywork-ml/test-bodywork-batch-job-project.git"  # noqa
        expected_output_2 = "Deployment successful"

        assert expected_output_1 in process.stdout
        assert expected_output_2 in process.stdout
        assert process.returncode == 0

    except Exception:
        print_completed_process_info(process)
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-batch-job-project")
        rmtree(SSH_DIR_NAME, ignore_errors=True)


def test_deployment_command_unsuccessful_raises_exception(test_namespace: str):
    with raises(CalledProcessError):
        run(
            [
                "bodywork",
                "create",
                "deployment",
                "http://bad.repo",
                "master",
            ],
            check=True,
        )


@mark.usefixtures("setup_cluster")
def test_cli_cronjob_handler_crud():
    try:
        process = run(
            [
                "bodywork",
                "create",
                "cronjob",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                "--name=bodywork-test-project",
                "--schedule=0,30 * * * *",
                "--retries=2",
                "--history-limit=1",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "Created cronjob=bodywork-test-project" in process.stdout
        assert process.returncode == 0

        process = run(
            [
                "bodywork",
                "update",
                "cronjob",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "main",
                "--name=bodywork-test-project",
                "--schedule=0,0 1 * * *",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "Updated cronjob=bodywork-test-project" in process.stdout
        assert process.returncode == 0

        process = run(
            ["bodywork", "get", "cronjob", "bodywork-test-project"],
            encoding="utf-8",
            capture_output=True,
        )
        assert "bodywork-test-project" in process.stdout
        assert "0,0 1 * * *" in process.stdout
        assert (
            "https://github.com/bodywork-ml/bodywork-test-project"
            in process.stdout
        )
        assert "main" in process.stdout
        assert process.returncode == 0

        process = run(
            [
                "bodywork",
                "delete",
                "cronjob",
                "bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "Deleted cronjob=bodywork-test-project" in process.stdout
        assert process.returncode == 0

        process = run(
            ["bodywork", "get", "cronjob"],
            encoding="utf-8",
            capture_output=True,
        )
        assert "" in process.stdout
        assert process.returncode == 0
    finally:
        run(
            [
                "kubectl",
                "delete",
                "cronjob",
                "bodywork-test-project",
                f"--namespace={BODYWORK_NAMESPACE}",
            ]
        )


@mark.usefixtures("setup_cluster")
def test_deployment_with_ssh_github_connectivity_from_file(
    docker_image: str,
    github_ssh_private_key_file: str,
):
    try:
        process = run(
            [
                "bodywork",
                "deployment",
                "create",
                "git@github.com:bodywork-ml/test-bodywork-batch-job-project.git",
                "master",
                f"--bodywork-docker-image={docker_image}",
                f"--ssh={github_ssh_private_key_file}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_1 = "deploying master branch from git@github.com:bodywork-ml/test-bodywork-batch-job-project.git"  # noqa
        expected_output_2 = "Deployment successful"
        assert expected_output_1 in process.stdout
        assert expected_output_2 in process.stdout
        assert process.returncode == 0
    except Exception:
        print_completed_process_info(process)
        assert False
    finally:
        load_kubernetes_config()
        if namespace_exists("bodywork-test-batch-job-project"):
            delete_namespace("bodywork-test-batch-job-project")
        rmtree(SSH_DIR_NAME, ignore_errors=True)


@mark.usefixtures("setup_cluster")
def test_deployment_of_remote_workflows(docker_image: str):
    try:
        job_name = "foo"

        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                "https://github.com/bodywork-ml/test-single-service-project.git",
                "master",
                f"--bodywork-image={docker_image}",
                "--async",
                f"--async-job-name={job_name}",
            ],
            encoding="utf-8",
            capture_output=True,
        )

        assert process.returncode == 0
        assert f"Created workflow-job=async-workflow-{job_name}" in process.stdout

        sleep(20)

        process = run(
            ["bodywork", "get", "deployments", "--async"],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0
        assert job_name in process.stdout

        process = run(
            [
                "bodywork",
                "get",
                "deployment",
                "--async",
                f"--logs=async-workflow-{job_name}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0
        assert type(process.stdout) is str and len(process.stdout) != 0
        assert "ERROR" not in process.stdout

    except Exception:
        print_completed_process_info(process)
        assert False
    finally:
        load_kubernetes_config()
        run(
            [
                "kubectl",
                "delete",
                "job",
                f"async-workflow-{job_name}",
                f"--namespace={BODYWORK_NAMESPACE}",
            ]
        )
        if namespace_exists("bodywork-test-single-service-project"):
            delete_namespace("bodywork-test-single-service-project")
        rmtree(SSH_DIR_NAME, ignore_errors=True)


@mark.usefixtures("setup_cluster")
def test_remote_deployment_with_ssh_github_connectivity(
    docker_image: str,
    set_github_ssh_private_key_env_var: None,
):
    job_name = "test-remote-ssh-workflow"
    try:
        process = run(
            [
                "bodywork",
                "create",
                "deployment",
                f"--name={job_name}",
                "--git-url=git@github.com:bodywork-ml/test-bodywork-batch-job-project.git",  # noqa
                "--git-branch=master",
                f"--bodywork-docker-image={docker_image}",
                f"--ssh={Path.home() / f'.ssh/{DEFAULT_SSH_FILE}'}",
                "--async",
                "--group=bodywork-tests",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0
        assert f"Created workflow-job={job_name}" in process.stdout

        sleep(5)

        process = run(
            [
                "bodywork",
                "deployment",
                "logs",
                f"--name={job_name}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process.returncode == 0
        assert type(process.stdout) is str and len(process.stdout) != 0
        assert "ERROR" or "error" not in process.stdout

    except Exception:
        print_completed_process_info(process)
        assert False
    finally:
        load_kubernetes_config()
        run(
            [
                "kubectl",
                "delete",
                "job",
                f"{job_name}",
                f"--namespace={BODYWORK_NAMESPACE}",
            ]
        )
        if namespace_exists("bodywork-test-batch-job-project"):
            delete_namespace("bodywork-test-batch-job-project")
        rmtree(SSH_DIR_NAME, ignore_errors=True)
