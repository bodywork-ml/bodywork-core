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
Pytest fixtures for use with all testing modules.
"""
import shutil
import os
import stat

from pytest import fixture
from pathlib import Path
from subprocess import run
from typing import Iterable
from bodywork.constants import (
    SSH_DIR_NAME,
    GIT_SSH_COMMAND,
)


@fixture(scope="function")
def project_repo_location() -> Path:
    return Path("tests/resources/project_repo")


@fixture(scope="function")
def cloned_project_repo_location() -> Path:
    return Path("bodywork_project")


@fixture(scope="function")
def bodywork_output_dir() -> Path:
    return Path("bodywork_project_output")


@fixture(scope="function")
def project_repo_connection_string(project_repo_location: Path) -> str:
    return project_repo_location.absolute().as_uri()


@fixture(scope="function")
def setup_bodywork_test_project(
    project_repo_location: Path,
    cloned_project_repo_location: Path,
    bodywork_output_dir: Path,
) -> Iterable[bool]:
    # SETUP
    try:
        run(["git", "init"], cwd=project_repo_location, check=True, encoding="utf-8")
        run(
            ["git", "add", "-A"],
            cwd=project_repo_location,
            check=True,
            encoding="utf-8",
        )
        run(
            ["git", "commit", "-m", '"test"'],
            cwd=project_repo_location,
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        os.mkdir(bodywork_output_dir)
        yield True
    except Exception as e:
        raise RuntimeError(f"Cannot create test project Git repo - {e}.")
    finally:
        # TEARDOWN
        if GIT_SSH_COMMAND in os.environ:
            del os.environ[GIT_SSH_COMMAND]
        ssh_dir = Path(".") / SSH_DIR_NAME
        if ssh_dir.exists():
            shutil.rmtree(ssh_dir, onerror=remove_readonly)
        if project_repo_location.exists():
            shutil.rmtree(f"{project_repo_location}/.git", onerror=remove_readonly)
        if cloned_project_repo_location.exists():
            shutil.rmtree(cloned_project_repo_location, onerror=remove_readonly)
        if bodywork_output_dir.exists():
            shutil.rmtree(bodywork_output_dir, onerror=remove_readonly)


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
