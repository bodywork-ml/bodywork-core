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
from unittest.mock import patch, MagicMock, mock_open
from subprocess import CalledProcessError
from pathlib import Path

from bodywork.exceptions import BodyworkGitError
from bodywork.constants import (
    SSH_PRIVATE_KEY_ENV_VAR,
    DEFAULT_PROJECT_DIR,
    GIT_SSH_COMMAND,
)
from bodywork.git import (
    ConnectionProtocol,
    download_project_code_from_repo,
    get_connection_protocol,
    setup_ssh_for_git_host,
    get_ssh_public_key_from_domain,
    get_git_commit_hash,
)


def test_that_git_project_clone_raises_exceptions():
    with raises(BodyworkGitError, match="Git clone failed"):
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
    with patch.object(Path, "exists") as mock_exists:
        mock_exists.return_value = False
        with raises(RuntimeError, match=f"Failed to setup SSH for {hostname}"):
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
        setup_ssh_for_git_host(hostname, "test_file")


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
def test_get_git_commit_hash_throws_bodyworkgiterror_on_fail(
    mock_run: MagicMock,
):
    with raises(BodyworkGitError, match="Unable to retrieve git commit hash:"):
        get_git_commit_hash()


@patch("bodywork.git.run", side_effect=OSError("Invalid Path"))
def test_get_git_commit_hash_throws_bodyworkgiterror_when_invalid_path(
    mock_run: MagicMock,
):
    with raises(
        BodyworkGitError,
        match=f"Unable to retrieve git commit hash, path: {DEFAULT_PROJECT_DIR}"
        f" is invalid - Invalid Path",
    ):
        get_git_commit_hash()


@patch("bodywork.git.run")
@patch("bodywork.git.get_ssh_public_key_from_domain")
@patch("bodywork.git.Path.touch")
@patch("bodywork.git.Path.mkdir")
@patch("bodywork.git.os")
def test_setup_ssh_for_git_host_create_known_host_and_env_var(
    mock_os: MagicMock,
    mock_mkdir: MagicMock,
    mock_touch: MagicMock,
    mock_get_ssh: MagicMock,
    mock_run: MagicMock,
):
    mock_os.environ = {SSH_PRIVATE_KEY_ENV_VAR: "MY_PRIVATE_KEY"}
    mock_get_ssh.return_value = "fingerprint"
    try:
        with patch.object(Path, "exists") as mock_exists:
            mock_exists.return_value = False
            with patch.object(Path, "open", mock_open()) as m:
                setup_ssh_for_git_host("github.com")

            handle = m()
            handle.write.assert_any_call("MY_PRIVATE_KEY\n")
            mock_get_ssh.assert_called_with("github.com")
            handle.write.assert_any_call("fingerprint")
    except Exception:
        assert False


@patch("bodywork.git.known_hosts_contains_domain_key")
@patch("bodywork.git.Path.exists")
@patch("bodywork.git.run")
def test_use_ssh_key_from_file(
    mock_run: MagicMock, mock_exists: MagicMock, mock_known_hosts: MagicMock
):

    download_project_code_from_repo(
        "git@github.com:bodywork-ml/test.git", ssh_key_path="SSH_key"
    )

    assert "SSH_key" in os.environ.get(GIT_SSH_COMMAND)
