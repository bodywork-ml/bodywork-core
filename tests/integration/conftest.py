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
Pytest fixtures for use with all Kubernetes integration testing modules.
"""
import os
import re
import stat
from pathlib import Path
from random import randint
from subprocess import PIPE, Popen, STDOUT
from typing import Iterable

from pytest import fixture
from _pytest.fixtures import FixtureRequest
from kubernetes import client as k8s_client, config as k8s_config
from subprocess import run

from bodywork.constants import (
    BODYWORK_DOCKERHUB_IMAGE_REPO,
    BODYWORK_WORKFLOW_CLUSTER_ROLE,
    SSH_PRIVATE_KEY_ENV_VAR,
    BODYWORK_NAMESPACE,
)
from bodywork.workflow_execution import image_exists_on_dockerhub
from bodywork.cli.setup_namespace import setup_namespace_with_service_accounts_and_roles
from bodywork.k8s.auth import load_kubernetes_config, workflow_cluster_role_binding_name
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
def set_github_ssh_private_key_env_var() -> Iterable[None]:
    private_key = Path.home() / ".ssh/id_rsa"
    if private_key.exists():
        os.environ[SSH_PRIVATE_KEY_ENV_VAR] = private_key.read_text()
    else:
        private_key = Path.home() / ".ssh/id_ed25519"
        if private_key.exists():
            os.environ[SSH_PRIVATE_KEY_ENV_VAR] = private_key.read_text()
        else:
            raise RuntimeError("Cannot locate private SSH key to use for GitHub.")
    yield None
    del os.environ[SSH_PRIVATE_KEY_ENV_VAR]


@fixture(scope="function")
def set_git_ssh_private_key_env_var() -> Iterable[None]:
    if "CIRCLECI" in os.environ:
        private_key = Path.home() / ".ssh" / "id_rsa_e28827a593edd69f1a58cf07a7755107"
    else:
        private_key = Path.home() / ".ssh" / "id_rsa"
        if not private_key.exists():
            private_key = Path.home() / ".ssh" / "id_ed25519"
    if private_key.exists():
        os.environ[SSH_PRIVATE_KEY_ENV_VAR] = private_key.read_text()
    else:
        raise RuntimeError("Cannot locate private SSH key to use.")
    yield None
    del os.environ[SSH_PRIVATE_KEY_ENV_VAR]


@fixture(scope="function")
def github_ssh_private_key_file(bodywork_output_dir: Path) -> Path:
    try:
        private_key = Path.home() / ".ssh/id_rsa"
        if not private_key.exists():
            private_key = Path.home() / ".ssh/id_ed25519"
        if not private_key.exists():
            raise RuntimeError("cannot locate private SSH key to use for GitHub")
        file_path = bodywork_output_dir / "id_bodywork"
        with Path(file_path).open(mode="w", newline="\n") as file_handle:
            file_handle.write(private_key.read_text())
        file_path.chmod(mode=stat.S_IREAD)
        return file_path
    except Exception as e:
        raise RuntimeError(f"Cannot create Github SSH Private Key File - {e}.")


@fixture(scope="session")
def ingress_load_balancer_url() -> Iterable[str]:
    try:
        k8s_config.load_kube_config()
        _, active_context = k8s_config.list_kube_config_contexts()
        if active_context["name"] == "minikube":
            mk_service_tunnel = Popen(
                [
                    "minikube",
                    "service",
                    "-n",
                    NGINX_INGRESS_CONTROLLER_NAMESPACE,
                    NGINX_INGRESS_CONTROLLER_SERVICE_NAME,
                    "--url",
                ],
                stdout=PIPE,
                stderr=STDOUT,
                text=True,
            )
            for line in mk_service_tunnel.stdout:
                ingress_url_match = re.search(r"http://(\d|\.)+:\d+", line)
                if ingress_url_match:
                    ingress_url = ingress_url_match.group()
                    break
            yield ingress_url
            mk_service_tunnel.kill()
        else:
            services_in_namespace = k8s_client.CoreV1Api().list_namespaced_service(
                namespace=NGINX_INGRESS_CONTROLLER_NAMESPACE
            )
            nginx_service = [
                service
                for service in services_in_namespace.items
                if service.metadata.name == NGINX_INGRESS_CONTROLLER_SERVICE_NAME
            ][0]
            ingress_url = nginx_service.status.load_balancer.ingress[0].hostname
            yield ingress_url
    except IndexError:
        msg = (
            f"Cannot find service={NGINX_INGRESS_CONTROLLER_SERVICE_NAME} in "
            f"namespace={NGINX_INGRESS_CONTROLLER_NAMESPACE}."
        )
        raise RuntimeError(msg)
    except AttributeError:
        msg = (
            f"Cannot find a load-balancer associated with "
            f"service={NGINX_INGRESS_CONTROLLER_SERVICE_NAME} in "
            f"namespace={NGINX_INGRESS_CONTROLLER_NAMESPACE}."
        )
        raise RuntimeError(msg)
    except k8s_client.rest.ApiException as e:
        msg = f"K8s API error - {e}"
        raise RuntimeError(msg)
    except Exception as e:
        raise RuntimeError() from e


@fixture(scope="session")
def setup_cluster(request: FixtureRequest) -> None:
    load_kubernetes_config()
    setup_namespace_with_service_accounts_and_roles(BODYWORK_NAMESPACE)
    create_namespace(TEST_NAMESPACE)

    def clean_up():
        delete_namespace(BODYWORK_NAMESPACE)
        k8s_client.RbacAuthorizationV1Api().delete_cluster_role(
            BODYWORK_WORKFLOW_CLUSTER_ROLE
        )
        k8s_client.RbacAuthorizationV1Api().delete_cluster_role_binding(
            workflow_cluster_role_binding_name(BODYWORK_NAMESPACE)
        )
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
            f"--namespace={BODYWORK_NAMESPACE}",
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
            f"--namespace={BODYWORK_NAMESPACE}",
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
                f"--namespace={BODYWORK_NAMESPACE}",
                "testsecrets-bodywork-test-project-credentials",
            ]
        )

    request.addfinalizer(delete_secrets)
