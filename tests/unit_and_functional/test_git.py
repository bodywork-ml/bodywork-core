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

from pytest import raises
from unittest.mock import patch, MagicMock
from subprocess import CalledProcessError

from bodywork.exceptions import BodyworkGitError
from bodywork.constants import SSH_PRIVATE_KEY_ENV_VAR
from bodywork.git import (
    ConnectionProtocol,
    download_project_code_from_repo,
    get_connection_protocol,
    setup_ssh_for_git_host,
    get_ssh_public_key_from_domain,
    get_git_commit_hash,
)


def test_that_git_project_clone_raises_exceptions():
    with raises(BodyworkGitError, match="git clone failed"):
        download_project_code_from_repo("file:///bad_url")


@patch("bodywork.git.setup_ssh_for_git_host")
def test_that_git_project_clone_returns_git_error_in_exception(
    mock_setup_ssh: MagicMock,
):
    with raises(BodyworkGitError, match="fatal: Could not read from remote repository"):
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


@patch("bodywork.git.Path.read_text")
@patch("bodywork.git.Path.exists")
def test_setup_ssh_for_github_raises_exception_on_known_hosts_file_exception(
    mock_path: MagicMock,
    mock_path_read: MagicMock,
):
    hostname = "github.com"
    mock_path_read.side_effect = OSError("Test Exception")

    with raises(
        RuntimeError,
        match=f"Error updating known hosts with public key from {hostname}",
    ):
        setup_ssh_for_git_host(hostname)


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


@patch("bodywork.git.run", side_effect=CalledProcessError(999, "git rev-parse"))
def test_get_git_commit_hash_throws_exception_on_fail(
    mock_run: MagicMock,
):
    with raises(BodyworkGitError, match=f"Unable to retrieve git commit hash:"):
        get_git_commit_hash()
