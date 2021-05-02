import shutil
import os
import stat

from pytest import fixture
from pathlib import Path
from subprocess import run
from typing import Iterable
from bodywork.constants import (
    SSH_DIR_NAME,
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
        if "GIT_SSH_COMMAND" in os.environ:
            del os.environ["GIT_SSH_COMMAND"]
        ssh_dir = Path(".") / SSH_DIR_NAME
        shutil.rmtree(ssh_dir, ignore_errors=True, onerror=on_error)
        shutil.rmtree(f"{project_repo_location}/.git", onerror=on_error)
        shutil.rmtree(
            f"{cloned_project_repo_location}/.git", ignore_errors=True, onerror=on_error
        )
        shutil.rmtree(
            cloned_project_repo_location, ignore_errors=True, onerror=on_error
        )
        shutil.rmtree(bodywork_output_dir, ignore_errors=True, onerror=on_error)


def on_error(func, path, exc_info):
    """Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=on_error)``
    """
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise Exception
