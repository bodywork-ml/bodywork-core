"""
Integration Tests for interactions with hosted Git repositories.
"""
import os
import shutil
import stat

from pathlib import Path
from typing import Iterable

from bodywork.git import download_project_code_from_repo, setup_ssh_for_git_host
from bodywork.constants import SSH_DIR_NAME, SSH_PRIVATE_KEY_ENV_VAR, GIT_SSH_COMMAND


def test_that_git_project_repo_can_be_cloned_from_github_using_ssh(
        setup_bodywork_test_project: Iterable[bool],
        github_repo_connection_string: str,
        cloned_project_repo_location: Path,
        set_github_ssh_private_key_env_var: None,
):
    try:
        download_project_code_from_repo(github_repo_connection_string)
        assert cloned_project_repo_location.exists()
    except Exception:
        assert False


def test_that_git_project_repo_can_be_cloned_from_gitlab_using_ssh(
        setup_bodywork_test_project: Iterable[bool],
        gitlab_repo_connection_string: str,
        cloned_project_repo_location: Path,
        set_gitlab_ssh_private_key_env_var: None,
):
    try:
        download_project_code_from_repo(gitlab_repo_connection_string)
        assert cloned_project_repo_location.exists()
    except Exception:
        assert False


def test_that_git_project_repo_can_be_cloned(
        setup_bodywork_test_project: Iterable[bool],
        project_repo_connection_string: str,
        cloned_project_repo_location: Path,
):
    try:
        download_project_code_from_repo(project_repo_connection_string)
        assert cloned_project_repo_location.exists()
    except Exception:
        assert False


def test_setup_ssh_for_git_host_create_known_host_and_env_var():
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

        assert os.environ[GIT_SSH_COMMAND][:3] == "ssh"
    except Exception:
        assert False
    finally:
        os.environ.pop(SSH_PRIVATE_KEY_ENV_VAR)
        os.environ.pop(GIT_SSH_COMMAND)
        shutil.rmtree(ssh_dir, onerror=remove_readonly)


def remove_readonly(func, path, exc_info):
    """Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file) it attempts to add write
    permission and then retries. If the error is for another reason it re-raises the
    error. This is primarily to fix Windows OS access issues.

    Usage: ``shutil.rmtree(path, onerror=remove_readonly)``
    """
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise Exception
