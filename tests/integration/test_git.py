"""
Integration Tests for interactions with hosted Git repositories.
"""
import shutil
from pathlib import Path
from typing import Iterable

from conftest import on_error

from bodywork.constants import SSH_DIR_NAME
from bodywork.git import download_project_code_from_repo


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
    finally:
        ssh_dir = Path(".") / SSH_DIR_NAME
        shutil.rmtree(ssh_dir, ignore_errors=True, onerror=on_error)


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
    finally:
        ssh_dir = Path(".") / SSH_DIR_NAME
        shutil.rmtree(ssh_dir, ignore_errors=True, onerror=on_error)
