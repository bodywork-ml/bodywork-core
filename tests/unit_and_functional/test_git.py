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
Tests for Git repository interaction functions.
"""
import os
import shutil
from pathlib import Path
from typing import Iterable

from pytest import raises
from unittest.mock import patch, MagicMock
from conftest import on_error

from bodywork.constants import SSH_DIR_NAME, SSH_PRIVATE_KEY_ENV_VAR
from bodywork.git import (
    ConnectionProtocol,
    download_project_code_from_repo,
    get_connection_protocol,
    setup_ssh_for_git_host,
    get_ssh_public_key_from_domain
)


def test_that_git_project_repo_can_be_cloned(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_connection_string: str,
    cloned_project_repo_location: Path
):
    try:
        download_project_code_from_repo(project_repo_connection_string)
        assert cloned_project_repo_location.exists()
    except Exception:
        assert False


def test_that_git_project_clone_raises_exceptions():
    with raises(RuntimeError, match="git clone failed"):
        download_project_code_from_repo("file:///bad_url")


@patch("bodywork.git.setup_ssh_for_git_host")
def test_that_git_project_clone_returns_git_error_in_exception(
    mock_setup_ssh: MagicMock,
):  # noqa
    with raises(RuntimeError, match="fatal: Could not read from remote repository"):
        download_project_code_from_repo("git@xyz.com:test/test.git")


def test_get_connection_protocol_identifies_connection_protocols():
    conn_str_1 = "https://github.com/bodywork-ml/bodywork-test-project"
    assert get_connection_protocol(conn_str_1) is ConnectionProtocol.HTTPS

    conn_str_2 = "git@github.com:bodywork-ml/bodywork-test-project.git"
    assert get_connection_protocol(conn_str_2) is ConnectionProtocol.SSH

    conn_str_3 = "file:///Users/alexioannides/Dropbox/data_science/workspace/python/bodywork"  # noqa
    assert get_connection_protocol(conn_str_3) is ConnectionProtocol.FILE


def test_get_connection_protocol_raises_exception_for_unknown_protocol():
    conn_str = "http://github.com/bodywork-ml/bodywork-test-project"
    with raises(RuntimeError, match="cannot identify connection protocol"):
        get_connection_protocol(conn_str)


def test_setup_ssh_for_github_raises_exception_no_private_key_env_var():
    hostname = "github.com"
    if os.environ.get(SSH_PRIVATE_KEY_ENV_VAR):
        del os.environ[SSH_PRIVATE_KEY_ENV_VAR]
    with raises(KeyError, match=f"failed to setup SSH for {hostname}"):
        setup_ssh_for_git_host(hostname)


def test_setup_ssh_for_git_host_create_known_host_and_env_var():
    if not os.environ.get(SSH_PRIVATE_KEY_ENV_VAR):
        os.environ[SSH_PRIVATE_KEY_ENV_VAR] = "MY_PRIVATE_KEY"

    ssh_dir = Path(".") / SSH_DIR_NAME
    try:
        assert ssh_dir.exists() is False
        setup_ssh_for_git_host("github.com")

        private_key = ssh_dir / "id_rsa"
        assert private_key.exists() is True
        assert private_key.read_text() == "MY_PRIVATE_KEY"

        known_hosts = ssh_dir / "known_hosts"
        assert known_hosts.exists() is True
        assert known_hosts.read_text()[:18] == "github.com ssh-rsa"

        assert os.environ["GIT_SSH_COMMAND"][:3] == "ssh"
    except Exception:
        assert False
    finally:
        shutil.rmtree(ssh_dir, ignore_errors=True, onerror=on_error)


@patch("bodywork.git.run")
def test_get_ssh_public_key_from_domain_throws_exception_if_ssh_fingerprints_do_not_match(
    mock_run: MagicMock,
):
    hostname = "github.com"

    with raises(
        ConnectionAbortedError,
        match=f"SECURITY ALERT! SSH Fingerprint received "
        f"from server does not match the fingerprint for {hostname}.",
    ):
        get_ssh_public_key_from_domain(hostname)
