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

from pytest import fixture

from bodywork.constants import BODYWORK_DOCKERHUB_IMAGE_REPO, SSH_GITHUB_KEY_ENV_VAR
from bodywork.workflow import image_exists_on_dockerhub


@fixture(scope='function')
def test_namespace() -> str:
    return 'bodywork-dev'


@fixture(scope='function')
def random_test_namespace() -> str:
    rand_test_namespace = f'bodywork-integration-tests-{randint(0, 10000)}'
    print(f'\n|--> Bodywork integration tests running in '
          f'namespace={rand_test_namespace}')
    return rand_test_namespace


@fixture(scope='function')
def docker_image() -> str:
    with open(Path('VERSION'), 'r') as file:
        version = file.readlines()[0].replace('\n', '')
    dev_image = f'{BODYWORK_DOCKERHUB_IMAGE_REPO}:{version}-dev'
    if image_exists_on_dockerhub(BODYWORK_DOCKERHUB_IMAGE_REPO, f'{version}-dev'):
        return dev_image
    else:
        raise RuntimeError(f'{dev_image} is not available for running integration tests')


@fixture(scope='function')
def set_github_ssh_private_key_env_var() -> None:
    try:
        os.environ[SSH_GITHUB_KEY_ENV_VAR]
    except KeyError:
        private_key = Path.home() / '.ssh/id_rsa'
        if private_key.exists():
            os.environ[SSH_GITHUB_KEY_ENV_VAR] = private_key.read_text()
        else:
            raise RuntimeError('cannot locate private SSH key to use for GitHub')
