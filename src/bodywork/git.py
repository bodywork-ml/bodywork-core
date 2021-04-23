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
from subprocess import run, CalledProcessError, DEVNULL, PIPE, Popen
from urllib.parse import urlparse

from .constants import DEFAULT_PROJECT_DIR, SSH_DIR_NAME, SSH_PRIVATE_KEY_ENV_VAR, \
    GITHUB_SSH_FINGERPRINT, GITLAB_SSH_FINGERPRINT, BITBUCKET_SSH_FINGERPRINT
from .logs import bodywork_log_factory


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
    log = bodywork_log_factory()
    try:
        run(['git', '--version'], check=True, stdout=DEVNULL)
    except CalledProcessError:
        raise RuntimeError('git is not available')
    try:
        if get_connection_protocol(url) is ConnectionPrototcol.SSH:
            setup_ssh_for_github(urlparse(url).hostname)
        elif SSH_PRIVATE_KEY_ENV_VAR not in os.environ:
            log.warning('Not configured for use with private GitHub repos')
    except Exception as e:
        msg = f'Unable to setup SSH for Github and you are trying to connect via SSH: {e}'  # noqa
        raise RuntimeError(msg)
    try:
        run(['git', 'clone', '--branch', branch, '--single-branch', url, destination],
            check=True, encoding='utf-8', stdout=DEVNULL, stderr=PIPE)
    except CalledProcessError as e:
        msg = f'git clone failed - calling {e.cmd} returned {e.stderr}'
        raise RuntimeError(msg)


class GitRepoHost(Enum):
    """Remote hosting service for Git repository."""
    GITHUB = 'github.com'
    GITLAB = 'gitlab.com'
    LOCAL_FS = 'file'


class ConnectionPrototcol(Enum):
    """Connection protocol used to access Git repo."""
    FILE = 'file'
    HTTPS = 'https'
    SSH = 'ssh'


def get_remote_repo_host(connection_string: str) -> GitRepoHost:
    """Derive the remote Git repo host from connection string.

    :param connection_string: The string containing the connection
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
    """Derive connection protocol used to retrieve Git repo.

    :param connection_string: The string containing the connection
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
               f'- currently, there is only support for HTTPS and SSH')
        raise RuntimeError(msg)


def setup_ssh_for_github(hostname: str) -> None:
    """Setup system for SSH interaction with GitHub.

    Using the private key assigned to an environment variable, this
    function creates a new SSH configuration in the working directory
    and then tells Git to use it for SSH by exporting the
    GIT_SSH_COMMAND environment variable.
    """
    ssh_dir = Path('.') / SSH_DIR_NAME
    private_key = ssh_dir / 'id_rsa'
    if not private_key.exists():
        if SSH_PRIVATE_KEY_ENV_VAR not in os.environ:
            msg = (f'failed to setup SSH for GitHub - cannot find '
                   f'{SSH_PRIVATE_KEY_ENV_VAR} environment variable')
            raise KeyError(msg)
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        private_key.touch(0o700, exist_ok=False)
        private_key.write_text(os.environ[SSH_PRIVATE_KEY_ENV_VAR])

    known_hosts = ssh_dir / 'known_hosts'
    if not known_hosts.exists() or not known_hosts_contains_domain_key(hostname):
        known_hosts.touch(0o700, exist_ok=False)
        known_hosts.write_text(get_ssh_public_key_from_domain(hostname))

    os.environ['GIT_SSH_COMMAND'] = (
        f'ssh -i {private_key} -o UserKnownHostsFile={known_hosts}'
    )


def known_hosts_contains_domain_key(hostname: str, known_hosts_filepath: Path) -> bool:
    return f'{hostname} ssh-rsa' in known_hosts_filepath.read_text()


def get_ssh_public_key_from_domain(hostname: str) -> str:
    fingerprints = {'github.com': GITHUB_SSH_FINGERPRINT, 'gitlab.com': GITLAB_SSH_FINGERPRINT,
                    'bitbucket.org': BITBUCKET_SSH_FINGERPRINT}
    if hostname in fingerprints:
        try:
            server_key = run(['ssh-keyscan', '-t', 'rsa', hostname], check=True, shell=True,
                             capture_output=True, encoding='utf-8').stdout
            fingerprint = run(['ssh-keygen', '-l', '-f', '-'], check=True, shell=True,
                              capture_output=True, encoding='utf-8', input=server_key).stdout.strip()
            if fingerprint == fingerprints.get(hostname):
                return server_key
            else:
                raise ConnectionAbortedError(
                    f'SECURITY ALERT! SSH Fingerprint received from server does not match the fingerprint for'
                    f' {hostname}. Please check and ensure that {hostname} is not being impersonated')
        except CalledProcessError as e:
            raise RuntimeError(f'Unable to retrieve public SSH key from {hostname}: {e.stderr}')
    else:
        raise RuntimeError(f'{hostname} is not supported by Bodywork')
