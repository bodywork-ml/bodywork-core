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
Integration tests for interactions with hosted Git repositories.
"""
from pathlib import Path
from typing import Iterable

from bodywork.git import download_project_code_from_repo, get_git_commit_hash


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
    set_git_ssh_private_key_env_var: None,
):
    try:
        download_project_code_from_repo(gitlab_repo_connection_string)
        assert cloned_project_repo_location.exists()
    except Exception:
        assert False


def test_that_git_project_repo_can_be_cloned_from_bitbucket_using_ssh(
    setup_bodywork_test_project: Iterable[bool],
    bitbucket_repo_connection_string: str,
    cloned_project_repo_location: Path,
    set_git_ssh_private_key_env_var: None,
):
    try:
        download_project_code_from_repo(bitbucket_repo_connection_string)
        assert cloned_project_repo_location.exists()
    except Exception:
        assert False


def test_that_git_project_repo_can_be_cloned_from_azure_using_ssh(
    setup_bodywork_test_project: Iterable[bool],
    azure_repo_connection_string: str,
    cloned_project_repo_location: Path,
    set_git_ssh_private_key_env_var: None,
):
    try:
        download_project_code_from_repo(azure_repo_connection_string)
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


def test_that_git_commit_hash_is_retrieved(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_location,
):
    try:
        result = get_git_commit_hash(project_repo_location)
        assert len(result) == 7
    except Exception:
        assert False
