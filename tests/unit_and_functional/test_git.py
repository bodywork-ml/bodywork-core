"""
Tests for Git repository interaction functions.
"""
import os
import shutil
from pathlib import Path
from typing import Iterable

from pytest import raises

from bodywork.constants import SSH_DIR_NAME, SSH_GITHUB_KEY_ENV_VAR
from bodywork.git import (
    ConnectionPrototcol,
    download_project_code_from_repo,
    get_connection_protocol,
    get_remote_repo_host,
    GitRepoHost,
    setup_ssh_for_github
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
    with raises(RuntimeError, match='git clone failed'):
        download_project_code_from_repo('file:///bad_url')


def test_get_remote_repo_host_identifies_remote_hosts():
    conn_str_1 = 'https://github.com/AlexIoannides/bodywork-test-project'
    assert get_remote_repo_host(conn_str_1) is GitRepoHost.GITHUB

    conn_str_2 = 'git@github.com:AlexIoannides/bodywork-test-project.git'
    assert get_remote_repo_host(conn_str_2) is GitRepoHost.GITHUB


def test_get_remote_repo_host_raises_exception_for_unknown_host():
    conn_str = ' https://bitbucket.org/8ffie/ml-and-statistics-python-jupyter-nb.git'
    with raises(RuntimeError, match='unknown Git repo host'):
        get_remote_repo_host(conn_str)


def test_get_connection_protocol_identifies_connection_protocols():
    conn_str_1 = 'https://github.com/AlexIoannides/bodywork-test-project'
    assert get_connection_protocol(conn_str_1) is ConnectionPrototcol.HTTPS

    conn_str_2 = 'git@github.com:AlexIoannides/bodywork-test-project.git'
    assert get_connection_protocol(conn_str_2) is ConnectionPrototcol.SSH

    conn_str_3 = 'file:///Users/alexioannides/Dropbox/data_science/workspace/python/bodywork'  # noqa
    assert get_connection_protocol(conn_str_3) is ConnectionPrototcol.FILE


def test_get_connection_protocol_raises_exception_for_unknown_protocol():
    conn_str = 'http://github.com/AlexIoannides/bodywork-test-project'
    with raises(RuntimeError, match='cannot identify connection protocol'):
        get_connection_protocol(conn_str)


def test_setup_ssh_for_github_raises_exception_no_private_key_env_var():
    if os.environ.get(SSH_GITHUB_KEY_ENV_VAR):
        del os.environ[SSH_GITHUB_KEY_ENV_VAR]
    with raises(RuntimeError, match='failed to setup SSH for GitHub'):
        setup_ssh_for_github()


def test_setup_ssh_for_github_create_ssh_files_and_env_var():
    if not os.environ.get(SSH_GITHUB_KEY_ENV_VAR):
        os.environ[SSH_GITHUB_KEY_ENV_VAR] = 'MY_PRIVATE_KEY'

    try:
        ssh_dir = Path('.') / SSH_DIR_NAME
        assert ssh_dir.exists() is False
        setup_ssh_for_github()

        private_key = ssh_dir / 'id_rsa'
        assert private_key.exists() is True
        assert private_key.read_text() == 'MY_PRIVATE_KEY'

        known_hosts = ssh_dir / 'known_hosts'
        assert known_hosts.exists() is True
        assert known_hosts.read_text()[:18] == 'github.com ssh-rsa'

        assert os.environ['GIT_SSH_COMMAND'][:3] == 'ssh'
    except Exception:
        assert False
    finally:
        shutil.rmtree(ssh_dir, ignore_errors=True)
