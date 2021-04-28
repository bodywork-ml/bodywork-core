"""
Integration Tests for interactions with hosted Git repositories.
"""
from pathlib import Path
from typing import Iterable

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
