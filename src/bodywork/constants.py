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
