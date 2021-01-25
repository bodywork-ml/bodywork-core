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
This module contains constant values (e.g. default values) to be shared
accoss all modules and tests as required. Constants should not be
defined within seperate modules as this can lead to duplications and
inconsistencies.
"""
from pathlib import Path

BODYWORK_DOCKERHUB_IMAGE_REPO = 'bodyworkml/bodywork-core'
BODYWORK_DOCKER_IMAGE = f'{BODYWORK_DOCKERHUB_IMAGE_REPO}:latest'
BODYWORK_WORKFLOW_CLUSTER_ROLE = 'bodywork-workflow-controller'
BODYWORK_WORKFLOW_SERVICE_ACCOUNT = 'bodywork-workflow-controller'
BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT = 'bodywork-jobs-and-deployments'
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_LOG_LEVEL_ENV_VAR = 'BODYWORK_LOG_LEVEL'
DEFAULT_PROJECT_DIR = Path('./bodywork_project')
PROJECT_CONFIG_FILENAME = 'bodywork.ini'
REQUIREMENTS_FILENAME = 'requirements.txt'
STAGE_CONFIG_FILENAME = 'config.ini'
SSH_DIR_NAME = '.ssh_bodywork'
SSH_GITHUB_KEY_ENV_VAR = 'BODYWORK_GITHUB_SSH_PRIVATE_KEY'
SSH_GITHUB_SECRET_NAME = 'ssh-github-private-key'
TIMEOUT_GRACE_SECONDS = 60
