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
import os
import requests
from shutil import rmtree
from subprocess import CalledProcessError, run
from time import sleep

from pytest import raises, mark

from bodywork.constants import (
    PROJECT_CONFIG_FILENAME,
    SSH_DIR_NAME,
    SSH_PRIVATE_KEY_ENV_VAR,
    SSH_SECRET_NAME,
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
    BODYWORK_WORKFLOW_CLUSTER_ROLE,
)
from bodywork.k8s import (
    cluster_role_binding_exists,
    delete_cluster_role_binding,
    delete_namespace,
    workflow_cluster_role_binding_name,
    load_kubernetes_config,
)


@mark.usefixtures("setup_cluster")
def test_workflow_and_service_management_end_to_end_from_cli(
 docker_image: str, ingress_load_balancer_url: str
):
    try:
        process_zero = run(
            ["bodywork", "setup-namespace", "bodywork-test-project"],
            encoding="utf-8",
            capture_output=True,
        )
        assert f"creating namespace=bodywork-test-project" in process_zero.stdout
        assert f"creating service-account={BODYWORK_WORKFLOW_SERVICE_ACCOUNT}" in process_zero.stdout
        assert f"creating cluster-role-binding={BODYWORK_WORKFLOW_CLUSTER_ROLE}" in process_zero.stdout
        assert process_zero.returncode == 0

        process_one = run(
            [
                "bodywork",
                "secret",
                "create",
                f"--namespace=bodywork-test-project",
                "--name=bodywork-test-project-credentials",
                "--data",
                "USERNAME=alex",
                "PASSWORD=alex123",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_one.stdout is not None
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
        expected_output_1 = (
            "attempting to run workflow for "
            "project=https://github.com/bodywork-ml/bodywork-test-project on "
            f"branch=master"
        )
        expected_output_2 = "successfully ran stage=stage_1"
        expected_output_3 = "attempting to run stage=stage_4"
        expected_output_4 = (
            "successfully ran workflow for "
            "project=https://github.com/bodywork-ml/bodywork-test-project on "
            f"branch=master"
        )
        expected_output_5 = "successfully ran stage=stage_5"
        assert expected_output_1 in process_two.stdout
        assert expected_output_2 in process_two.stdout
        assert expected_output_3 in process_two.stdout
        assert expected_output_4 in process_two.stdout
        assert expected_output_5 in process_two.stdout
        assert process_two.returncode == 0

        process_three = run(
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
        assert process_three.returncode == 0

        process_four = run(
            ["bodywork", "service", "display", f"--namespace=bodywork-test-project"],
            encoding="utf-8",
            capture_output=True,
        )
        assert (
            f"http://bodywork-test-project--stage-3.bodywork-test-project.svc"
            in process_four.stdout
        )
        assert (
            f"http://bodywork-test-project--stage-4.bodywork-test-project.svc"
            in process_four.stdout
        )
        assert (
            f"/bodywork-test-project/bodywork-test-project--stage-3"
            in process_four.stdout
        )
        assert (
            f"/bodywork-test-project/bodywork-test-project--stage-4"
            not in process_four.stdout
        )
        assert "5000" in process_four.stdout
        assert process_four.returncode == 0

        stage_3_service_external_url = (
            f"http://{ingress_load_balancer_url}/bodywork-test-project/"
            f"/bodywork-test-project--stage-3/v1/predict"
        )

        response_stage_3 = requests.get(url=stage_3_service_external_url)
        assert response_stage_3.ok
        assert response_stage_3.json()["y"] == "hello_world"

        stage_4_service_external_url = (
            f"http://{ingress_load_balancer_url}/bodywork-test-project/"
            f"/bodywork-test-project--stage-4/v2/predict"
        )
        response_stage_4 = requests.get(url=stage_4_service_external_url)
        assert response_stage_4.status_code == 404

        process_five = run(
            [
                "bodywork",
                "service",
                "delete",
                f"--namespace=bodywork-test-project",
                "--name=bodywork-test-project--stage-3",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert (
            "deployment=bodywork-test-project--stage-3 deleted" in process_five.stdout
        )
        assert (
            f"service at http://bodywork-test-project--stage-3.bodywork-test-project.svc.cluster.local deleted"  # noqa
            in process_five.stdout
        )  # noqa
        assert (
            f"ingress route /bodywork-test-project/bodywork-test-project--stage-3 deleted"  # noqa
            in process_five.stdout
        )
        assert process_five.returncode == 0

        process_six = run(
            [
                "bodywork",
                "service",
                "delete",
                f"--namespace=bodywork-test-project",
                "--name=bodywork-test-project--stage-4",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert "deployment=bodywork-test-project--stage-4 deleted" in process_six.stdout
        assert (
            f"service at http://bodywork-test-project--stage-4.bodywork-test-project.svc.cluster.local deleted"  # noqa
            in process_six.stdout
        )  # noqa
        assert (
            f"ingress route /bodywork-test-project/bodywork-test-project--stage-4 deleted"  # noqa
            not in process_six.stdout
        )  # noqa
        assert process_six.returncode == 0

        process_seven = run(
            ["bodywork", "service", "display", f"--namespace=bodywork-test-project"],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_seven.stdout == ""
        assert process_seven.returncode == 0

    except Exception as e:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-project")
        workflow_sa_crb = workflow_cluster_role_binding_name("bodywork-test-project")
        if cluster_role_binding_exists(workflow_sa_crb):
            delete_cluster_role_binding(workflow_sa_crb)


def test_workflow_will_cleanup_jobs_and_rollback_new_deployments_that_yield_errors(
    random_test_namespace: str, docker_image: str
):
    try:
        process_zero = run(
            ["bodywork", "setup-namespace", "bodywork-rollback-deployment-test-project"],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_zero.returncode == 0

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
        expected_output_0 = (
            "deleted job=bodywork-rollback-deployment-test-project--stage-1"  # noqa
        )
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
        expected_output_1 = "deployments failed to roll-out successfully"
        expected_output_2 = "rolled back deployment=bodywork-rollback-deployment-test-project--stage-2"  # noqa
        assert expected_output_1 in process_two.stdout
        assert expected_output_2 in process_two.stdout
        assert process_two.returncode == 1

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-rollback-deployment-test-project")
        workflow_sa_crb = workflow_cluster_role_binding_name("bodywork-rollback-deployment-test-project")
        if cluster_role_binding_exists(workflow_sa_crb):
            delete_cluster_role_binding(workflow_sa_crb)


@mark.usefixtures("setup_cluster")
def test_workflow_will_run_failure_stage_on_workflow_failure(
    test_namespace: str, docker_image: str
):
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

        expected_output_0 = "ERROR - workflow_execution.run_workflow - failed to execute workflow for master branch"  # noqa
        expected_output_1 = "successfully ran stage=on_fail_stage"
        expected_output_2 = "I have successfully been executed"
        assert expected_output_0 in process_one.stdout
        assert expected_output_1 in process_one.stdout
        assert expected_output_2 in process_one.stdout
        assert process_one.returncode == 1
    except Exception:
        assert False


@mark.usefixtures("setup_cluster")
def test_workflow_will_not_run_if_bodywork_docker_image_cannot_be_located(
    test_namespace: str,
):
    process_one = run(
        [
            "bodywork",
            "workflow",
            "https://github.com/bodywork-ml/bodywork-test-project",
            "master",
            "--bodywork-docker-image=bad:bodyworkml/bodywork-core:0.0.0",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        f"invalid DOCKER_IMAGE specified in {PROJECT_CONFIG_FILENAME}"
        in process_one.stdout
    )
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
        "cannot locate bodyworkml/bodywork-not-an-image:latest on DockerHub"
        in process_two.stdout
    )
    assert process_two.returncode == 1


def test_workflow_with_ssh_github_connectivity(
    random_test_namespace: str,
    docker_image: str,
    set_github_ssh_private_key_env_var: None,
):
    try:
        sleep(5)

        process_zero = run(
            ["bodywork", "setup-namespace", "bodywork-test-project"],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_zero.returncode == 0

        process_one = run(
            [
                "bodywork",
                "secret",
                "create",
                f"--namespace=bodywork-test-project",
                f"--name={SSH_SECRET_NAME}",
                "--data",
                f"{SSH_PRIVATE_KEY_ENV_VAR}={os.environ[SSH_PRIVATE_KEY_ENV_VAR]}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_one.stdout is not None
        assert process_one.returncode == 0

        process_two = run(
            [
                "bodywork",
                "secret",
                "create",
                f"--namespace=bodywork-test-project",
                "--name=bodywork-test-project-credentials",
                "--data",
                "USERNAME=alex",
                "PASSWORD=alex123",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_two.stdout is not None
        assert process_two.returncode == 0

        process_three = run(
            [
                "bodywork",
                "workflow",
                "git@github.com:bodywork-ml/bodywork-test-project.git",
                "master",
                f"--bodywork-docker-image={docker_image}",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        expected_output_1 = (
            "attempting to run workflow for "
            "project=git@github.com:bodywork-ml/bodywork-test-project.git on "
            f"branch=master"
        )
        expected_output_2 = (
            "successfully ran workflow for "
            "project=git@github.com:bodywork-ml/bodywork-test-project.git on "
            f"branch=master"
        )
        expected_output_3 = "successfully ran stage=stage_1"
        assert expected_output_1 in process_three.stdout
        assert expected_output_2 in process_three.stdout
        assert expected_output_3 in process_three.stdout
        assert process_three.returncode == 0

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace("bodywork-test-project")
        rmtree(SSH_DIR_NAME, ignore_errors=True)


def test_cli_secret_handler_crud(test_namespace: str):
    process_zero = run(
        ["bodywork", "setup-namespace", test_namespace],
        encoding="utf-8",
        capture_output=True,
    )
    assert process_zero.returncode == 0

    process_one = run(
        [
            "bodywork",
            "secret",
            "create",
            f"--namespace={test_namespace}",
            "--name=pytest-credentials",
            "--data",
            "USERNAME=alex",
            "PASSWORD=alex123",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "secret=pytest-credentials created" in process_one.stdout
    assert process_one.returncode == 0

    process_two = run(
        [
            "bodywork",
            "secret",
            "display",
            f"--namespace={test_namespace}",
            "--name=pytest-credentials",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "USERNAME=alex" in process_two.stdout
    assert "PASSWORD=alex123" in process_two.stdout
    assert process_two.returncode == 0

    process_three = run(
        [
            "bodywork",
            "secret",
            "delete",
            f"--namespace={test_namespace}",
            "--name=pytest-credentials",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "secret=pytest-credentials deleted" in process_three.stdout
    assert process_three.returncode == 0

    process_four = run(
        [
            "bodywork",
            "secret",
            "display",
            f"--namespace={test_namespace}",
            "--name=pytest-credentials",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "" in process_four.stdout
    assert process_four.returncode == 0


def test_deployment_of_remote_workflows(random_test_namespace: str):
    try:
        process_one = run(
            [
                "bodywork",
                "deployment",
                "create",
                "--name=bodywork-test-project",
                "--git-repo-url=https://github.com/bodywork-ml/bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_one.returncode == 0

        sleep(5)

        process_two = run(
            [
                "bodywork",
                "deployment",
                "display",
                "--name=bodywork-test-project",
            ],
            encoding="utf-8",
            capture_output=True,
        )
        assert process_two.returncode == 0
        assert "bodywork-test-project" in process_two.stdout

        process_three = run(
            [
                "bodywork",
                "deployment",
                "logs",
                "--name=bodywork-test-project",
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
        rmtree(SSH_DIR_NAME, ignore_errors=True)


@mark.usefixtures("setup_cluster")
def test_cli_cronjob_handler_crud(test_namespace: str):
    process_one = run(
        [
            "bodywork",
            "cronjob",
            "create",
            "--name=bodywork-test-project",
            "--schedule=0,30 * * * *",
            "--git-repo-url=https://github.com/bodywork-ml/bodywork-test-project",
            "--retries=2",
            "--history-limit=1",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "cronjob=bodywork-test-project created" in process_one.stdout
    assert process_one.returncode == 0

    process_two = run(
        ["bodywork", "cronjob", "display"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "bodywork-test-project" in process_two.stdout
    assert "0,30 * * * *" in process_two.stdout
    assert "https://github.com/bodywork-ml/bodywork-test-project" in process_two.stdout
    assert "master" in process_two.stdout
    assert process_two.returncode == 0

    process_three = run(
        [
            "bodywork",
            "cronjob",
            "delete",
            "--name=bodywork-test-project",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "cronjob=bodywork-test-project deleted" in process_three.stdout
    assert process_three.returncode == 0

    process_four = run(
        ["bodywork", "cronjob", "display"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "" in process_four.stdout
    assert process_four.returncode == 0


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
