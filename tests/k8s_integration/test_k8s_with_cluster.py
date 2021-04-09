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

from pytest import raises

from bodywork.constants import (
    PROJECT_CONFIG_FILENAME,
    SSH_DIR_NAME,
    SSH_GITHUB_KEY_ENV_VAR,
    SSH_GITHUB_SECRET_NAME
)
from bodywork.k8s import (
    cluster_role_binding_exists,
    delete_cluster_role_binding,
    delete_namespace,
    workflow_cluster_role_binding_name,
    load_kubernetes_config
)


def test_workflow_and_service_management_end_to_end_from_cli(
    random_test_namespace: str,
    docker_image: str,
    ingress_load_balancer_url: str
):
    try:
        sleep(5)

        process_zero = run(
            ['bodywork',
             'setup-namespace',
             random_test_namespace],
            encoding='utf-8',
            capture_output=True
        )
        assert f'creating namespace={random_test_namespace}' in process_zero.stdout
        assert 'creating service-account=bodywork-workflow-' in process_zero.stdout
        assert 'creating cluster-role-binding=bodywork-workflow-' in process_zero.stdout
        assert 'creating service-account=bodywork-jobs-' in process_zero.stdout
        assert process_zero.returncode == 0

        process_one = run(
            ['bodywork',
             'secret',
             'create',
             f'--namespace={random_test_namespace}',
             '--name=bodywork-test-project-credentials',
             '--data',
             'USERNAME=alex',
             'PASSWORD=alex123'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_one.stdout is not None
        assert process_one.returncode == 0

        process_two = run(
            ['bodywork',
             'workflow',
             f'--namespace={random_test_namespace}',
             'https://github.com/bodywork-ml/bodywork-test-project',
             'master',
             f'--bodywork-docker-image={docker_image}'],
            encoding='utf-8',
            capture_output=True
        )
        expected_output_1 = (
            'attempting to run workflow for '
            'project=https://github.com/bodywork-ml/bodywork-test-project on '
            f'branch=master in kubernetes namespace={random_test_namespace}')
        expected_output_2 = 'successfully ran stage=stage_1'
        expected_output_3 = 'attempting to run stage=stage_4'
        expected_output_4 = (
            'successfully ran workflow for '
            'project=https://github.com/bodywork-ml/bodywork-test-project on '
            f'branch=master in kubernetes namespace={random_test_namespace}')
        expected_output_5 = 'successfully ran stage=stage_5'
        assert expected_output_1 in process_two.stdout
        assert expected_output_2 in process_two.stdout
        assert expected_output_3 in process_two.stdout
        assert expected_output_4 in process_two.stdout
        assert expected_output_5 in process_two.stdout
        assert process_two.returncode == 0

        process_three = run(
            ['bodywork',
             'workflow',
             f'--namespace={random_test_namespace}',
             'https://github.com/bodywork-ml/bodywork-test-project',
             'master',
             f'--bodywork-docker-image={docker_image}'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_three.returncode == 0

        process_four = run(
            ['bodywork',
             'service',
             'display',
             f'--namespace={random_test_namespace}'],
            encoding='utf-8',
            capture_output=True
        )
        assert (f'http://bodywork-test-project--stage-3.{random_test_namespace}.svc'
                in process_four.stdout)
        assert (f'http://bodywork-test-project--stage-4.{random_test_namespace}.svc'
                in process_four.stdout)
        assert (f'/{random_test_namespace}/bodywork-test-project--stage-3'
                in process_four.stdout)
        assert (f'/{random_test_namespace}/bodywork-test-project--stage-4'
                not in process_four.stdout)
        assert '5000' in process_four.stdout
        assert process_four.returncode == 0

        stage_3_service_external_url = (
            f'http://{ingress_load_balancer_url}/{random_test_namespace}/'
            f'/bodywork-test-project--stage-3/v1/predict'
        )

        response_stage_3 = requests.get(url=stage_3_service_external_url)
        assert response_stage_3.ok
        assert response_stage_3.json()['y'] == 'hello_world'

        stage_4_service_external_url = (
            f'http://{ingress_load_balancer_url}/{random_test_namespace}/'
            f'/bodywork-test-project--stage-4/v2/predict'
        )
        response_stage_4 = requests.get(url=stage_4_service_external_url)
        assert response_stage_4.status_code == 404

        process_five = run(
            ['bodywork',
             'service',
             'delete',
             f'--namespace={random_test_namespace}',
             '--name=bodywork-test-project--stage-3'],
            encoding='utf-8',
            capture_output=True
        )
        assert 'deployment=bodywork-test-project--stage-3 deleted' in process_five.stdout
        assert f'service at http://bodywork-test-project--stage-3.{random_test_namespace}.svc.cluster.local deleted' in process_five.stdout  # noqa
        assert f'ingress route /{random_test_namespace}/bodywork-test-project--stage-3 deleted' in process_five.stdout  # noqa
        assert process_five.returncode == 0

        process_six = run(
            ['bodywork',
             'service',
             'delete',
             f'--namespace={random_test_namespace}',
             '--name=bodywork-test-project--stage-4'],
            encoding='utf-8',
            capture_output=True
        )
        assert 'deployment=bodywork-test-project--stage-4 deleted' in process_six.stdout
        assert f'service at http://bodywork-test-project--stage-4.{random_test_namespace}.svc.cluster.local deleted' in process_six.stdout  # noqa
        assert f'ingress route /{random_test_namespace}/bodywork-test-project--stage-4 deleted' not in process_six.stdout  # noqa
        assert process_six.returncode == 0

        process_seven = run(
            ['bodywork',
             'service',
             'display',
             f'--namespace={random_test_namespace}'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_seven.stdout == ''
        assert process_seven.returncode == 0

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace(random_test_namespace)
        workflow_sa_crb = workflow_cluster_role_binding_name(random_test_namespace)
        if cluster_role_binding_exists(workflow_sa_crb):
            delete_cluster_role_binding(workflow_sa_crb)


def test_workflow_will_cleanup_jobs_and_rollback_new_deployments_that_yield_errors(
    random_test_namespace: str,
    docker_image: str
):
    try:
        sleep(5)

        process_zero = run(
            ['bodywork',
             'setup-namespace',
             random_test_namespace],
            encoding='utf-8',
            capture_output=True
        )
        assert process_zero.returncode == 0

        process_one = run(
            ['bodywork',
             'workflow',
             f'--namespace={random_test_namespace}',
             'https://github.com/bodywork-ml/bodywork-rollback-deployment-test-project',  # noqa
             'master',
             f'--bodywork-docker-image={docker_image}'],
            encoding='utf-8',
            capture_output=True
        )
        expected_output_0 = 'deleted job=bodywork-rollback-deployment-test-project--stage-1'  # noqa
        assert expected_output_0 in process_one.stdout
        assert process_one.returncode == 0

        process_two = run(
            ['bodywork',
             'workflow',
             f'--namespace={random_test_namespace}',
             'https://github.com/bodywork-ml/bodywork-rollback-deployment-test-project',  # noqa
             'master',
             f'--bodywork-docker-image={docker_image}'],
            encoding='utf-8',
            capture_output=True
        )
        expected_output_1 = 'deployments failed to roll-out successfully'
        expected_output_2 = 'rolled back deployment=bodywork-rollback-deployment-test-project--stage-2'  # noqa
        assert expected_output_1 in process_two.stdout
        assert expected_output_2 in process_two.stdout
        assert process_two.returncode == 1

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace(random_test_namespace)
        workflow_sa_crb = workflow_cluster_role_binding_name(random_test_namespace)
        if cluster_role_binding_exists(workflow_sa_crb):
            delete_cluster_role_binding(workflow_sa_crb)


def test_workflow_will_not_run_if_namespace_is_not_setup_for_bodywork(
    random_test_namespace: str
):
    process_one = run(
        ['bodywork',
            'workflow',
            f'--namespace={random_test_namespace}',
            'https://github.com/bodywork-ml/bodywork-test-project',
            'master'],
        encoding='utf-8',
        capture_output=True
    )
    assert f'{random_test_namespace} is not setup for use' in process_one.stdout
    assert process_one.returncode == 1


def test_workflow_will_not_run_if_bodywork_docker_image_cannot_be_located(
    test_namespace: str
):
    process_one = run(
        ['bodywork',
            'workflow',
            f'--namespace={test_namespace}',
            'https://github.com/bodywork-ml/bodywork-test-project',
            'master',
            '--bodywork-docker-image=bad:bodyworkml/bodywork-core:0.0.0'],
        encoding='utf-8',
        capture_output=True
    )
    assert (f'invalid DOCKER_IMAGE specified in {PROJECT_CONFIG_FILENAME}'
            in process_one.stdout)
    assert process_one.returncode == 1

    process_two = run(
        ['bodywork',
            'workflow',
            f'--namespace={test_namespace}',
            'https://github.com/bodywork-ml/bodywork-test-project',
            'master',
            '--bodywork-docker-image=bodyworkml/bodywork-not-an-image:latest'],
        encoding='utf-8',
        capture_output=True
    )
    assert ('cannot locate bodyworkml/bodywork-not-an-image:latest on DockerHub'
            in process_two.stdout)
    assert process_two.returncode == 1


def test_workflow_with_ssh_github_connectivity(
    random_test_namespace: str,
    docker_image: str,
    set_github_ssh_private_key_env_var: None
):
    try:
        sleep(5)

        process_zero = run(
            ['bodywork',
             'setup-namespace',
             random_test_namespace],
            encoding='utf-8',
            capture_output=True
        )
        assert process_zero.returncode == 0

        process_one = run(
            ['bodywork',
             'secret',
             'create',
             f'--namespace={random_test_namespace}',
             f'--name={SSH_GITHUB_SECRET_NAME}',
             '--data',
             f'{SSH_GITHUB_KEY_ENV_VAR}={os.environ[SSH_GITHUB_KEY_ENV_VAR]}'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_one.stdout is not None
        assert process_one.returncode == 0

        process_two = run(
            ['bodywork',
             'secret',
             'create',
             f'--namespace={random_test_namespace}',
             '--name=bodywork-test-project-credentials',
             '--data',
             'USERNAME=alex',
             'PASSWORD=alex123'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_two.stdout is not None
        assert process_two.returncode == 0

        process_three = run(
            ['bodywork',
             'workflow',
             f'--namespace={random_test_namespace}',
             'git@github.com:bodywork-ml/bodywork-test-project.git',
             'master',
             f'--bodywork-docker-image={docker_image}'],
            encoding='utf-8',
            capture_output=True
        )
        expected_output_1 = (
            'attempting to run workflow for '
            'project=git@github.com:bodywork-ml/bodywork-test-project.git on '
            f'branch=master in kubernetes namespace={random_test_namespace}')
        expected_output_2 = (
            'successfully ran workflow for '
            'project=git@github.com:bodywork-ml/bodywork-test-project.git on '
            f'branch=master in kubernetes namespace={random_test_namespace}')
        expected_output_3 = 'successfully ran stage=stage_1'
        assert expected_output_1 in process_three.stdout
        assert expected_output_2 in process_three.stdout
        assert expected_output_3 in process_three.stdout
        assert process_three.returncode == 0

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace(random_test_namespace)
        rmtree(SSH_DIR_NAME, ignore_errors=True)


def test_cli_secret_handler_crud(test_namespace: str):
    process_one = run(
        ['bodywork',
         'secret',
         'create',
         f'--namespace={test_namespace}',
         '--name=pytest-credentials',
         '--data',
         'USERNAME=alex',
         'PASSWORD=alex123'],
        encoding='utf-8',
        capture_output=True
    )
    assert 'secret=pytest-credentials created' in process_one.stdout
    assert process_one.returncode == 0

    process_two = run(
        ['bodywork',
         'secret',
         'display',
         f'--namespace={test_namespace}',
         '--name=pytest-credentials'],
        encoding='utf-8',
        capture_output=True
    )
    assert 'USERNAME=alex' in process_two.stdout
    assert 'PASSWORD=alex123' in process_two.stdout
    assert process_two.returncode == 0

    process_three = run(
        ['bodywork',
         'secret',
         'delete',
         f'--namespace={test_namespace}',
         '--name=pytest-credentials'],
        encoding='utf-8',
        capture_output=True
    )
    assert 'secret=pytest-credentials deleted' in process_three.stdout
    assert process_three.returncode == 0

    process_four = run(
        ['bodywork',
         'secret',
         'display',
         f'--namespace={test_namespace}',
         '--name=pytest-credentials'],
        encoding='utf-8',
        capture_output=True
    )
    assert '' in process_four.stdout
    assert process_four.returncode == 0


def test_deployment_will_not_be_created_if_namespace_is_not_setup_for_bodywork(
    random_test_namespace: str
):
    process_one = run(
        ['bodywork',
         'deployment',
         'create',
         f'--namespace={random_test_namespace}',
         '--name=bodywork-test-project',
         '--git-repo-url=https://github.com/bodywork-ml/bodywork-test-project'],
        encoding='utf-8',
        capture_output=True
    )
    assert f'{random_test_namespace} is not setup for use' in process_one.stdout
    assert process_one.returncode == 1


def test_deployment_of_remote_workflows(
    random_test_namespace: str
):
    try:
        sleep(5)

        process_zero = run(
            ['bodywork',
             'setup-namespace',
             random_test_namespace],
            encoding='utf-8',
            capture_output=True
        )
        assert process_zero.returncode == 0

        process_one = run(
            ['bodywork',
             'deployment',
             'create',
             f'--namespace={random_test_namespace}',
             '--name=bodywork-test-project',
             '--git-repo-url=https://github.com/bodywork-ml/bodywork-test-project'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_one.returncode == 0

        sleep(5)

        process_two = run(
            ['bodywork',
             'deployment',
             'display',
             f'--namespace={random_test_namespace}',
             '--name=bodywork-test-project'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_two.returncode == 0
        assert 'bodywork-test-project' in process_two.stdout

        process_three = run(
            ['bodywork',
             'deployment',
             'logs',
             f'--namespace={random_test_namespace}',
             '--name=bodywork-test-project'],
            encoding='utf-8',
            capture_output=True
        )
        assert process_three.returncode == 0
        assert type(process_three.stdout) is str and len(process_three.stdout) != 0
        assert 'ERROR' not in process_three.stdout

    except Exception:
        assert False
    finally:
        load_kubernetes_config()
        delete_namespace(random_test_namespace)
        rmtree(SSH_DIR_NAME, ignore_errors=True)


def test_cronjob_will_not_be_created_if_namespace_is_not_setup_for_bodywork(
    random_test_namespace: str
):
    process_one = run(
        ['bodywork',
         'cronjob',
         'create',
         f'--namespace={random_test_namespace}',
         '--name=bodywork-test-project',
         '--schedule=0,30 * * * *',
         '--git-repo-url=https://github.com/bodywork-ml/bodywork-test-project'],
        encoding='utf-8',
        capture_output=True
    )
    assert f'{random_test_namespace} is not setup for use' in process_one.stdout
    assert process_one.returncode == 1


def test_cli_cronjob_handler_crud(test_namespace: str):
    process_one = run(
        ['bodywork',
         'cronjob',
         'create',
         f'--namespace={test_namespace}',
         '--name=bodywork-test-project',
         '--schedule=0,30 * * * *',
         '--git-repo-url=https://github.com/bodywork-ml/bodywork-test-project'
         '--retries=2',
         '--history-limit=1'],
        encoding='utf-8',
        capture_output=True
    )
    assert 'cronjob=bodywork-test-project created' in process_one.stdout
    assert process_one.returncode == 0

    process_two = run(
        ['bodywork',
         'cronjob',
         'display',
         f'--namespace={test_namespace}'],
        encoding='utf-8',
        capture_output=True
    )
    assert 'bodywork-test-project' in process_two.stdout
    assert '0,30 * * * *' in process_two.stdout
    assert 'https://github.com/bodywork-ml/bodywork-test-project' in process_two.stdout
    assert 'master' in process_two.stdout
    assert process_two.returncode == 0

    process_three = run(
        ['bodywork',
         'cronjob',
         'delete',
         f'--namespace={test_namespace}',
         '--name=bodywork-test-project'],
        encoding='utf-8',
        capture_output=True
    )
    assert 'cronjob=bodywork-test-project deleted' in process_three.stdout
    assert process_three.returncode == 0

    process_four = run(
        ['bodywork',
         'cronjob',
         'display',
         f'--namespace={test_namespace}'],
        encoding='utf-8',
        capture_output=True
    )
    assert '' in process_four.stdout
    assert process_four.returncode == 0


def test_workflow_command_unsuccessful_raises_exception(test_namespace: str):
    with raises(CalledProcessError):
        run(['bodywork',
             'workflow',
             f'--namespace={test_namespace}',
             'http://bad.repo',
             'master'],
            check=True)
