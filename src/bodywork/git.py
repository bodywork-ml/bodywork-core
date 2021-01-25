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
This module contains functions for downloading Bodywork projects from
Git repositories.
"""
import os
import re
from enum import Enum
from pathlib import Path
from subprocess import run, CalledProcessError

from .constants import DEFAULT_PROJECT_DIR, SSH_DIR_NAME, SSH_GITHUB_KEY_ENV_VAR


def download_project_code_from_repo(
    url: str,
    branch: str = 'master',
    destination: Path = DEFAULT_PROJECT_DIR
) -> None:
    """Download Bodywork project code from Git repository,

    :param url: Git repository URL.
    :param branch: The Git branch to download, defaults to 'master'.
    :param destination: The name of the directory int which the
        repository will be cloned, defaults to DEFAULT_PROJECT_DIR.
    :raises RuntimeError: If Git is not available on the system or the
        Git repository cannot be accessed.
    """
    try:
        run(['git', '--version'], check=True)
    except CalledProcessError:
        raise RuntimeError('git is not available')

    if (get_connection_protocol(url) is ConnectionPrototcol.SSH
            and get_remote_repo_host(url) is GitRepoHost.GITHUB):
        setup_ssh_for_github()

    try:
        run(['git', 'clone', '--branch', branch, '--single-branch', url, destination],
            check=True)
    except CalledProcessError as e:
        msg = f'git clone failed - calling {e.cmd} returned {e.stderr}'
        raise RuntimeError(msg)


class GitRepoHost(Enum):
    """Remote hosting service for Git repository."""
    GITHUB = 'github.com'
    LOCAL_FS = 'file'


class ConnectionPrototcol(Enum):
    """Conenction protocol used to access Git repo."""
    FILE = 'file'
    HTTPS = 'https'
    SSH = 'ssh'


def get_remote_repo_host(connection_string: str) -> GitRepoHost:
    """Derive the remote Git repo host from connection string.

    :param connection_string: The string contaiing the connection
        details for the remote Git repository - e.g. the GitHUb URL.
    :raises RuntimeError: if the remote Git repository cannot be
        determined.
    :return: The remote Git host type.
    """
    github = True if connection_string.find('github.com') != -1 else False
    if github:
        return GitRepoHost.GITHUB
    else:
        msg = 'unknown Git repo host - only remote repos on GitHub currently supported.'
        raise RuntimeError(msg)


def get_connection_protocol(connection_string: str) -> ConnectionPrototcol:
    """Derive connection protocol used to retreive Git repo.

    :param connection_string: The string contaiing the connection
        details for the remote Git repository - e.g. the GitHUb URL.
    :raises RuntimeError: if the connection protocol cannot be
        identified or is not supported.
    :return: The connection protocol type.
    """
    if re.match('^https://', connection_string):
        return ConnectionPrototcol.HTTPS
    elif re.match('^git@', connection_string):
        return ConnectionPrototcol.SSH
    elif re.match('^file://', connection_string):
        return ConnectionPrototcol.FILE
    else:
        msg = (f'cannot identify connection protocol in {connection_string}'
               f'- currently, there is only support for HTTPS and SSL')
        raise RuntimeError(msg)


def setup_ssh_for_github() -> None:
    """Setup system for SSH interaction with GitHub.

    Using the private key assigned to an environment variable, this
    function creates a new SSH configuration in the working directory
    and then tells Git to use it for SSH by exporting the
    GIT_SSH_COMMAND environment variable.
    """
    ssh_dir = Path('.') / SSH_DIR_NAME
    private_key = ssh_dir / 'id_rsa'
    if not private_key.exists():
        try:
            ssh_private_key = os.environ[SSH_GITHUB_KEY_ENV_VAR]
        except KeyError as e:
            msg = (f'failed to setup SSH for GitHub - cannot find '
                   f'{SSH_GITHUB_KEY_ENV_VAR} environment variable')
            raise RuntimeError(msg) from e
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        private_key.touch(0o700, exist_ok=False)
        private_key.write_text(ssh_private_key)

    known_hosts = ssh_dir / 'known_hosts'
    if not known_hosts.exists():
        ssh_public_key = 'github.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ=='  # noqa
        known_hosts.touch(0o700, exist_ok=False)
        known_hosts.write_text(ssh_public_key)

    os.environ['GIT_SSH_COMMAND'] = (
        f'ssh -i {private_key} -o UserKnownHostsFile={known_hosts}'
    )
