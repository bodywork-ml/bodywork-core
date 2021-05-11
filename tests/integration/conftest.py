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


from pytest import fixture
from kubernetes import client as k8s, config as k8s_config

from bodywork.constants import (
    BODYWORK_DOCKERHUB_IMAGE_REPO,
    SSH_PRIVATE_KEY_ENV_VAR,
)
from bodywork.workflow_execution import image_exists_on_dockerhub

NGINX_INGRESS_CONTROLLER_NAMESPACE = "ingress-nginx"
NGINX_INGRESS_CONTROLLER_SERVICE_NAME = "ingress-nginx-controller"


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
    return "git@ssh.dev.azure.com:v3/Bodyworkml/test-repos/test-repos"


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
    return "bodywork-dev"


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
        raise RuntimeError("cannot locate private SSH key to use for GitLab")


@fixture(scope="function")
def ingress_load_balancer_url() -> str:
    try:
        k8s_config.load_kube_config()
        services_in_namespace = k8s.CoreV1Api().list_namespaced_service(
            namespace=NGINX_INGRESS_CONTROLLER_NAMESPACE
        )
        nginx_service = [
            service
            for service in services_in_namespace.items
            if service.metadata.name == NGINX_INGRESS_CONTROLLER_SERVICE_NAME
        ][0]
        load_balancer = nginx_service.status.load_balancer.ingress[0].hostname
        return cast(str, load_balancer)
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
    except k8s.rest.ApiException as e:
        msg = f"k8s API error - {e}"
        raise RuntimeError(msg)
    except Exception as e:
        raise RuntimeError() from e
