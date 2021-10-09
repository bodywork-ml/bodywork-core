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
from subprocess import CalledProcessError, run
from time import sleep

from pytest import raises, mark

from bodywork.constants import SSH_DIR_NAME, BODYWORK_DEPLOYMENT_JOBS_NAMESPACE
from bodywork.k8s import (
    cluster_role_binding_exists,
    delete_cluster_role_binding,
    delete_namespace,
    workflow_cluster_role_binding_name,
    load_kubernetes_config,
)


@mark.usefixtures("add_secrets")
def test_workflow_and_service_management_end_to_end_from_cli(
    docker_image: str, ingress_load_balancer_url: str
):
    try:
        process_one = run(
            [
                "bodywork",
                "workflow",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                f"--bodywork-docker-image={docker_image}",
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

        assert findall(expected_output_1, process_one.stdout)
        assert findall(expected_output_2, process_one.stdout)
        assert findall(expected_output_3, process_one.stdout)
        assert findall(expected_output_4, process_one.stdout)
        assert findall(expected_output_5, process_one.stdout)
        assert findall(expected_output_6, process_one.stdout)
        assert findall(expected_output_7, process_one.stdout)
        assert process_one.returncode == 0

        process_two = run(
            [
                "bodywork",
                "workflow",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                f"--bodywork-docker-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_two.returncode == 0

        process_three = run(
            ["bodywork", "deployment", "display", "--namespace=bodywork-test-project"],
            encoding="utf-8",
            capture_output=True,
        )

        assert "stage-3" in process_three.stdout
        assert "stage-4" in process_three.stdout
        assert process_three.returncode == 0

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

        process_four = run(
            [
                "bodywork",
                "deployment",
                "delete",
                "--name=bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "deployment=bodywork-test-project deleted." in process_four.stdout

        assert process_four.returncode == 0

        sleep(5)

        process_five = run(
            [
                "bodywork",
                "deployment",
                "display",
                "--name=bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "No deployments found" in process_five.stdout
        assert process_five.returncode == 0

    except Exception as e:  # noqa
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-project")
        workflow_sa_crb = workflow_cluster_role_binding_name("bodywork-test-project")
        if cluster_role_binding_exists(workflow_sa_crb):
            delete_cluster_role_binding(workflow_sa_crb)


def test_services_from_previous_deployments_are_deleted():
    try:
        process_one = run(
            [
                "bodywork",
                "deployment",
                "create",
                "--git-url=https://github.com/bodywork-ml/test-single-service-project.git",
                "--git-branch=test-two-services",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_one.returncode == 0
        assert "Deployment successful" in process_one.stdout

        sleep(5)

        process_two = run(
            [
                "bodywork",
                "deployment",
                "create",
                "--git-url=https://github.com/bodywork-ml/test-single-service-project.git",
                "--git-branch=master",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_two.returncode == 0
        assert "Deployment successful" in process_two.stdout
        assert (
            "Removing service: stage-2 from previous deployment with git-commit-hash"  # noqa
            in process_two.stdout
        )

        process_three = run(
            [
                "bodywork",
                "deployment",
                "display",
                "--name=bodywork-test-single-service-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_three.returncode == 0
        assert "stage-1" in process_three.stdout
        assert "stage-2" not in process_three.stdout

    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-single-service-project")


def test_workflow_will_cleanup_jobs_and_rollback_new_deployments_that_yield_errors(
    docker_image: str,
):
    try:
        process_one = run(
            [
                "bodywork",
                "workflow",
                "https://github.com/bodywork-ml/bodywork-rollback-deployment-test-project",  # noqa
                "master",
                f"--bodywork-docker-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_0 = "Deleted k8s job for stage = stage-1"  # noqa
        assert expected_output_0 in process_one.stdout
        assert process_one.returncode == 0

        process_two = run(
            [
                "bodywork",
                "workflow",
                "https://github.com/bodywork-ml/bodywork-rollback-deployment-test-project",  # noqa
                "master",
                f"--bodywork-docker-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_1 = "Deployments failed to roll-out successfully"
        expected_output_2 = "Rolled-back k8s deployment for stage = stage-2"  # noqa
        assert expected_output_1 in process_two.stdout
        assert expected_output_2 in process_two.stdout
        assert process_two.returncode == 1

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-rollback-deployment-test-project")
        workflow_sa_crb = workflow_cluster_role_binding_name(
            "bodywork-rollback-deployment-test-project"
        )
        if cluster_role_binding_exists(workflow_sa_crb):
            delete_cluster_role_binding(workflow_sa_crb)


def test_workflow_will_run_failure_stage_on_workflow_failure(docker_image: str):
    try:
        process_one = run(
            [
                "bodywork",
                "workflow",
                "https://github.com/bodywork-ml/bodywork-failing-test-project",  # noqa
                "master",
                f"--bodywork-docker-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )

        expected_output_0 = "Deployment failed --> "
        expected_output_1 = "Completed k8s job for stage = on-fail-stage"
        expected_output_2 = "I have successfully been executed"
        assert expected_output_0 in process_one.stdout
        assert expected_output_1 in process_one.stdout
        assert expected_output_2 in process_one.stdout
        assert process_one.returncode == 1
    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-failing-test-project")


def test_workflow_will_not_run_if_bodywork_docker_image_cannot_be_located():
    try:
        bad_image = "bad:bodyworkml/bodywork-core:0.0.0"
        process_one = run(
            [
                "bodywork",
                "workflow",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                f"--bodywork-docker-image={bad_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert f"Invalid Docker image specified: {bad_image}" in process_one.stdout
        assert process_one.returncode == 1

        process_two = run(
            [
                "bodywork",
                "workflow",
                "https://github.com/bodywork-ml/bodywork-test-project",
                "master",
                "--bodywork-docker-image=bodyworkml/bodywork-not-an-image:latest",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert (
            "Cannot locate bodyworkml/bodywork-not-an-image:latest on DockerHub"
            in process_two.stdout
        )
        assert process_two.returncode == 1
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-project")


def test_workflow_with_ssh_github_connectivity(
    docker_image: str,
    set_github_ssh_private_key_env_var: None,
):
    try:
        process_one = run(
            [
                "bodywork",
                "workflow",
                "git@github.com:bodywork-ml/test-bodywork-batch-job-project.git",
                "master",
                f"--bodywork-docker-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_1 = "deploying master branch from git@github.com:bodywork-ml/test-bodywork-batch-job-project.git"  # noqa
        expected_output_2 = "Deployment successful"

        assert expected_output_1 in process_one.stdout
        assert expected_output_2 in process_one.stdout
        assert process_one.returncode == 0

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-batch-job-project")
        rmtree(SSH_DIR_NAME, ignore_errors=True)


def test_workflow_command_unsuccessful_raises_exception(test_namespace: str):
    with raises(CalledProcessError):
        run(
            [
                "bodywork",
                "workflow",
                f"--namespace={test_namespace}",
                "http://bad.repo",
                "master",
            ],
            check=True,
        )


def test_cli_cronjob_handler_crud():
    try:
        process_one = run(
            [
                "bodywork",
                "cronjob",
                "create",
                "--name=bodywork-test-project",
                "--schedule=0,30 * * * *",
                "--git-url=https://github.com/bodywork-ml/bodywork-test-project",
                "--retries=2",
                "--history-limit=1",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "Created cronjob=bodywork-test-project" in process_one.stdout
        assert process_one.returncode == 0

        process_two = run(
            [
                "bodywork",
                "cronjob",
                "update",
                "--name=bodywork-test-project",
                "--schedule=0,0 1 * * *",
                "--git-url=https://github.com/bodywork-ml/bodywork-test-project",
                "--git-branch=main",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "Updated cronjob=bodywork-test-project" in process_two.stdout
        assert process_two.returncode == 0

        process_three = run(
            ["bodywork", "cronjob", "display", "--name=bodywork-test-project"],
            encoding="utf-8",
            capture_output=True,
        )
        assert "bodywork-test-project" in process_three.stdout
        assert "0,0 1 * * *" in process_three.stdout
        assert (
            "https://github.com/bodywork-ml/bodywork-test-project"
            in process_three.stdout
        )  # noqa
        assert "main" in process_three.stdout
        assert process_three.returncode == 0

        process_four = run(
            [
                "bodywork",
                "cronjob",
                "delete",
                "--name=bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "Deleted cronjob=bodywork-test-project" in process_four.stdout
        assert process_four.returncode == 0

        process_five = run(
            ["bodywork", "cronjob", "display"],
            encoding="utf-8",
            capture_output=True,
        )
        assert "" in process_five.stdout
        assert process_five.returncode == 0
    finally:
        run(
            [
                "kubectl",
                "delete",
                "cronjobs",
                "bodywork-test-project",
                f"--namespace={BODYWORK_DEPLOYMENT_JOBS_NAMESPACE}",
            ]
        )


def test_deployment_of_remote_workflows(docker_image: str):
    job_name = "test-remote-workflows"
    try:
        process_one = run(
            [
                "bodywork",
                "deployment",
                "create",
                f"--name={job_name}",
                "--git-url=https://github.com/bodywork-ml/test-single-service-project.git",
                f"--bodywork-docker-image={docker_image}",
                "--async",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_one.returncode == 0
        assert f"Created workflow-job={job_name}" in process_one.stdout

        sleep(20)

        process_two = run(
            [
                "bodywork",
                "deployment",
                "display",
                "--name=bodywork-test-single-service-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_two.returncode == 0
        assert "bodywork-test-single-service-project" in process_two.stdout

        process_three = run(
            [
                "bodywork",
                "deployment",
                "logs",
                f"--name={job_name}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_three.returncode == 0
        assert type(process_three.stdout) is str and len(process_three.stdout) != 0
        assert "ERROR" not in process_three.stdout

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        run(
            [
                "kubectl",
                "delete",
                "job",
                f"{job_name}",
                f"--namespace={BODYWORK_DEPLOYMENT_JOBS_NAMESPACE}",
            ]
        )
        delete_namespace("bodywork-test-single-service-project")
        rmtree(SSH_DIR_NAME, ignore_errors=True)
