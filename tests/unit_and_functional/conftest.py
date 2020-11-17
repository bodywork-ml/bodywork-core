"""
Pytest fixtures for use with all unit and functional testing modules.
"""
import os
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Iterable

from pytest import fixture


@fixture(scope='function')
def project_repo_location() -> Path:
    return Path('tests/resources/project_repo')


@fixture(scope='function')
def project_repo_connection_string(project_repo_location: Path) -> str:
    return f'file://{project_repo_location.absolute()}'


@fixture(scope='function')
def cloned_project_repo_location() -> Path:
    return Path('bodywork_project')


@fixture(scope='function')
def bodywork_output_dir() -> Path:
    return Path('bodywork_project_output')


@fixture(scope='function')
def setup_bodywork_test_project(
    project_repo_location: Path,
    cloned_project_repo_location: Path,
    bodywork_output_dir: Path
) -> Iterable[bool]:
    # SETUP
    try:
        run(['git', 'init'], cwd=project_repo_location, check=True)
        run(['git', 'add', '-A'], cwd=project_repo_location, check=True)
        run(['git', 'commit', '-m', '"test"'], cwd=project_repo_location, check=True)
        run(['mkdir', bodywork_output_dir], check=True)
    except CalledProcessError as e:
        raise RuntimeError(f'Cannot create test project Git repo - {e}.')
    yield True
    # TEARDOWN
    run(['rm', '-rf', '.git'], cwd=project_repo_location)
    run(['rm', '-rf', cloned_project_repo_location])
    run(['rm', '-rf', bodywork_output_dir])


@fixture(scope='function')
def k8s_env_vars() -> Iterable[bool]:
    try:
        os.environ['KUBERNETES_SERVICE_HOST']
    except KeyError:
        os.environ['KUBERNETES_SERVICE_HOST'] = 'FOO'
    finally:
        yield True
    del os.environ['KUBERNETES_SERVICE_HOST']
