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
def test_namespace() -> str:
    return "bodywork-dev"


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
        shutil.rmtree(ssh_dir, onerror=remove_readonly)
        shutil.rmtree(f"{project_repo_location}/.git", onerror=remove_readonly)
        shutil.rmtree(
            f"{cloned_project_repo_location}/.git", onerror=remove_readonly
        )
        shutil.rmtree(
            cloned_project_repo_location, onerror=remove_readonly
        )
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
