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
across all modules and tests as required. Constants should not be
defined within separate modules as this can lead to duplications and
inconsistencies.
"""
import pkg_resources
from pathlib import Path

BODYWORK_CONFIG_VERSION = "1.0"
BODYWORK_DOCKERHUB_IMAGE_REPO = "bodyworkml/bodywork-core"
BODYWORK_DOCKER_IMAGE = f"{BODYWORK_DOCKERHUB_IMAGE_REPO}:latest"
BODYWORK_VERSION = pkg_resources.get_distribution("bodywork").version
BODYWORK_WORKFLOW_CLUSTER_ROLE = "bodywork-workflow-controller"
BODYWORK_WORKFLOW_SERVICE_ACCOUNT = "bodywork-workflow-controller"
BODYWORK_WORKFLOW_JOB_TIME_TO_LIVE = 15 * 60
BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT = "bodywork-jobs-and-deployments"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_LEVEL_ENV_VAR = "BODYWORK_LOG_LEVEL"
DEFAULT_PROJECT_DIR = Path("./bodywork_project")
FAILURE_EXCEPTION_K8S_ENV_VAR = "EXCEPTION_MESSAGE"
GIT_SSH_COMMAND = "GIT_SSH_COMMAND"
GIT_COMMIT_HASH_K8S_ENV_VAR = "GIT_COMMIT_HASH"
PROJECT_CONFIG_FILENAME = "bodywork.yaml"
SSH_DIR_NAME = ".ssh_bodywork"
SSH_PRIVATE_KEY_ENV_VAR = "BODYWORK_GIT_SSH_PRIVATE_KEY"
SSH_SECRET_NAME = "ssh-git-private-key"
TIMEOUT_GRACE_SECONDS = 90
USAGE_STATS_SERVER_URL = "http://a9c1ef555dfcc4fa3897c9468920f8b7-032e5dc531a766e1.elb.eu-west-2.amazonaws.com/bodywork-ml/usage-tracking--server/workflow-execution-counter"  # noqa

# External SSH Fingerprints
GITHUB_SSH_FINGERPRINT = (
    "2048 SHA256:nThbg6kXUpJWGl7E1IGOCspRomTxdCARLviKw6E5SY8 github.com (RSA)"  # noqa
)
GITLAB_SSH_FINGERPRINT = (
    "2048 SHA256:ROQFvPThGrW4RuWLoL9tq9I9zJ42fK4XywyRtbOz/EQ gitlab.com (RSA)"  # noqa
)
BITBUCKET_SSH_FINGERPRINT = "2048 SHA256:zzXQOXSRBEiUtuE8AikJYKwbHaxvSc0ojez9YXaGp1A bitbucket.org (RSA)"  # noqa
AZURE_SSH_FINGERPRINT = "2048 SHA256:ohD8VZEXGWo6Ez8GSEJQ9WpafgLFsOfLOtGGQCQo6Og ssh.dev.azure.com (RSA)"  # noqa
