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
Pytest fixtures for use with all Kubernetes integration testing modules.
"""
import os
from pathlib import Path
from random import randint
from typing import cast
from urllib.parse import urlparse

from pytest import fixture
from _pytest.fixtures import FixtureRequest
from kubernetes import client as k8s_client, config as k8s_config
from subprocess import run

from bodywork.constants import (
    BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
    BODYWORK_DOCKERHUB_IMAGE_REPO,
    BODYWORK_WORKFLOW_CLUSTER_ROLE,
    SSH_PRIVATE_KEY_ENV_VAR,
)
from bodywork.workflow_execution import image_exists_on_dockerhub
from bodywork.cli.setup_namespace import setup_namespace_with_service_accounts_and_roles
from bodywork.k8s.auth import load_kubernetes_config
from bodywork.k8s.namespaces import create_namespace, delete_namespace


NGINX_INGRESS_CONTROLLER_NAMESPACE = "ingress-nginx"
NGINX_INGRESS_CONTROLLER_SERVICE_NAME = "ingress-nginx-controller"
TEST_NAMESPACE = "bodywork-test"


@fixture(scope="function")
def gitlab_repo_connection_string() -> str:
    return "git@gitlab.com:bodyworkml/test-project.git"


@fixture(scope="function")
def github_repo_connection_string() -> str:
    return "git@github.com:bodywork-ml/private-test-repo.git"


@fixture(scope="function")
def bitbucket_repo_connection_string() -> str:
    return "git@bitbucket.org:bodywork/private-test-repo.git"


@fixture(scope="function")
def azure_repo_connection_string() -> str:
    return "git@ssh.dev.azure.com:v3/Bodyworkml/test-repos/private-test-repos"


@fixture(scope="function")
def random_test_namespace() -> str:
    rand_test_namespace = f"bodywork-integration-tests-{randint(0, 10000)}"
    print(
        f"\n|--> Bodywork integration tests running in "
        f"namespace={rand_test_namespace}"
    )
    return rand_test_namespace


@fixture(scope="function")
def test_namespace() -> str:
    return TEST_NAMESPACE


@fixture(scope="function")
def docker_image() -> str:
    with open(Path("VERSION"), "r") as file:
        version = file.readlines()[0].replace("\n", "")
    dev_image = f"{BODYWORK_DOCKERHUB_IMAGE_REPO}:{version}-dev"
    if image_exists_on_dockerhub(BODYWORK_DOCKERHUB_IMAGE_REPO, f"{version}-dev"):
        return dev_image
    else:
        raise RuntimeError(
            f"{dev_image} is not available for running integration tests"
        )


@fixture(scope="function")
def set_github_ssh_private_key_env_var() -> None:
    private_key = Path.home() / ".ssh/id_rsa"
    if private_key.exists():
        os.environ[SSH_PRIVATE_KEY_ENV_VAR] = private_key.read_text()
    else:
        raise RuntimeError("cannot locate private SSH key to use for GitHub")


@fixture(scope="function")
def set_git_ssh_private_key_env_var() -> None:
    if "CIRCLECI" in os.environ:
        private_key = Path.home() / ".ssh/id_rsa_e28827a593edd69f1a58cf07a7755107"
    else:
        private_key = Path.home() / ".ssh/id_rsa"
    if private_key.exists():
        os.environ[SSH_PRIVATE_KEY_ENV_VAR] = private_key.read_text()
    else:
        raise RuntimeError("cannot locate private SSH key to use")


@fixture(scope="function")
def ingress_load_balancer_url() -> str:
    try:
        k8s_config.load_kube_config()
        contexts, active_context = k8s_config.list_kube_config_contexts()
        if active_context["name"] == "minikube":
            kube_config = k8s_client.configuration.Configuration.get_default_copy()
            url = urlparse(kube_config.host).hostname
        else:
            services_in_namespace = k8s_client.CoreV1Api().list_namespaced_service(
                namespace=NGINX_INGRESS_CONTROLLER_NAMESPACE
            )
            nginx_service = [
                service
                for service in services_in_namespace.items
                if service.metadata.name == NGINX_INGRESS_CONTROLLER_SERVICE_NAME
            ][0]
            url = nginx_service.status.load_balancer.ingress[0].hostname
        return cast(str, url)
    except IndexError:
        msg = (
            f"cannot find service={NGINX_INGRESS_CONTROLLER_SERVICE_NAME} in "
            f"namespace={NGINX_INGRESS_CONTROLLER_NAMESPACE}"
        )
        raise RuntimeError(msg)
    except AttributeError:
        msg = (
            f"cannot find a load-balancer associated with "
            f"service={NGINX_INGRESS_CONTROLLER_SERVICE_NAME} in "
            f"namespace={NGINX_INGRESS_CONTROLLER_NAMESPACE}"
        )
        raise RuntimeError(msg)
    except k8s_client.rest.ApiException as e:
        msg = f"k8s API error - {e}"
        raise RuntimeError(msg)
    except Exception as e:
        raise RuntimeError() from e


@fixture(scope="session")
def setup_cluster(request: FixtureRequest) -> None:
    load_kubernetes_config()
    setup_namespace_with_service_accounts_and_roles(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE)
    create_namespace(TEST_NAMESPACE)

    def clean_up():
        # delete_namespace(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE)
        # k8s_client.RbacAuthorizationV1Api().delete_cluster_role(
        #     BODYWORK_WORKFLOW_CLUSTER_ROLE
        # )
        # k8s_client.RbacAuthorizationV1Api().delete_cluster_role_binding(
        #     f"{BODYWORK_WORKFLOW_CLUSTER_ROLE}--{BODYWORK_DEPLOYMENT_JOBS_NAMESPACE}"
        # )
        delete_namespace(TEST_NAMESPACE)

    request.addfinalizer(clean_up)


@fixture(scope="function")
def add_secrets(request: FixtureRequest) -> None:
    run(
        [
            "kubectl",
            "create",
            "secret",
            "generic",
            f"--namespace={BODYWORK_DEPLOYMENT_JOBS_NAMESPACE}",
            "testsecrets-bodywork-test-project-credentials",
            "--from-literal=USERNAME=alex",
            "--from-literal=PASSWORD=alex123",
        ]
    )

    run(
        [
            "kubectl",
            "label",
            "secret",
            f"--namespace={BODYWORK_DEPLOYMENT_JOBS_NAMESPACE}",
            "testsecrets-bodywork-test-project-credentials",
            "group=testsecrets",
        ]
    )

    def delete_secrets():
        run(
            [
                "kubectl",
                "delete",
                "secret",
                f"--namespace={BODYWORK_DEPLOYMENT_JOBS_NAMESPACE}",
                "testsecrets-bodywork-test-project-credentials",
            ]
        )

    request.addfinalizer(delete_secrets)
