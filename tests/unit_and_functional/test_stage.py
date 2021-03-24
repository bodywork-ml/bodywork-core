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
Test Bodywork project stage execution.
"""
from pathlib import Path
from typing import Iterable

from pytest import raises

from bodywork.exceptions import BodyworkStageFailure
from bodywork.stage import _install_python_requirements, run_stage


def test_that_requirements_can_be_installed(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_location: Path
):
    path_to_requirements = (
        project_repo_location
        / 'stage_3'
        / 'requirements.txt'
    )
    try:
        _install_python_requirements(path_to_requirements)
        assert True
    except Exception:
        assert False


def test_that_requirements_install_errors_raise_exception(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_location: Path
):
    path_to_requirements = (
        project_repo_location
        / 'stage_2_bad_config'
        / 'requirements.txt'
    )
    with raises(RuntimeError, match=r'requirements'):
        _install_python_requirements(path_to_requirements)


def test_run_stage(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_connection_string: str,
    bodywork_output_dir: Path
):
    try:
        run_stage('stage_1', project_repo_connection_string)
        assert True
    except Exception:
        assert False

    try:
        with open(bodywork_output_dir / 'stage_1_test_file.txt') as f:
            stage_output = f.read()
        assert stage_output.find('Hello from stage 1') != -1
        assert stage_output.find('numpy.sum(numpy.ones(10))=10') != 1
    except FileNotFoundError:
        assert False


def test_run_stage_failure_raises_exception(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_connection_string: str,
    bodywork_output_dir: Path
):
    with raises(BodyworkStageFailure, match=r'stage_3_bad_script'):
        run_stage('stage_3_bad_script', project_repo_connection_string)
