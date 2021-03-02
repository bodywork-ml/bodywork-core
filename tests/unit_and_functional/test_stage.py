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

from bodywork.config import BodyworkConfig
from bodywork.constants import STAGE_CONFIG_FILENAME
from bodywork.exceptions import BodyworkStageConfigError, BodyworkStageFailure
from bodywork.stage import (
    _install_python_requirements,
    BatchStage,
    run_stage,
    ServiceStage,
    Stage,
    stage_factory
)


def test_stage_factory_yields_stage_data_for_valid_stage(project_repo_location: Path):
    path_to_stage_dir = project_repo_location / 'stage_1_good'
    try:
        stage_factory(path_to_stage_dir)
        assert True
    except Exception:
        assert False


def test_stage_factory_yields_correct_data_for_batch_stages(project_repo_location: Path):
    path_to_stage_dir = project_repo_location / 'stage_1_good'
    stage_info = stage_factory(path_to_stage_dir)
    assert stage_info.path_to_stage_dir == path_to_stage_dir
    assert type(stage_info.config) == BodyworkConfig
    assert stage_info.executable_script_path == path_to_stage_dir / 'main.py'
    assert stage_info.name == 'stage_1_good'
    assert type(stage_info) == BatchStage
    assert stage_info.retries == 4
    assert stage_info.max_completion_time == 60


def test_stage_factory_yields_correct_data_for_service_stages(
    project_repo_location: Path
):
    path_to_stage_dir = project_repo_location / 'stage_5_good'
    stage_info = stage_factory(path_to_stage_dir)
    assert stage_info.path_to_stage_dir == path_to_stage_dir
    assert type(stage_info.config) == BodyworkConfig
    assert stage_info.executable_script_path == path_to_stage_dir / 'main.py'
    assert stage_info.name == 'stage_5_good'
    assert type(stage_info) == ServiceStage
    assert stage_info.replicas == 2
    assert stage_info.max_startup_time == 60
    assert stage_info.port == 5000


def test_stage_factory_raises_errors_for_invalid_stage_directories(
    project_repo_location: Path
):
    with raises(FileExistsError, match='does not exist'):
        path_to_stage_dir = project_repo_location / 'not_a_stage'
        stage_factory(path_to_stage_dir)
    with raises(BodyworkStageConfigError, match='STAGE_TYPE'):
        path_to_stage_dir = project_repo_location / 'stage_6_bad_stage_type'
        stage_factory(path_to_stage_dir)


def test_generic_stage_input_validation(project_repo_location: Path):
    stage_name = 'stage_16_bad_executable_script'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='EXECUTABLE_SCRIPT'):
        Stage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_2_bad_config'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(FileExistsError, match='Cannot find'):
        Stage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_17_bad_requirements'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(FileExistsError, match='Cannot find'):
        Stage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_18_bad_memory_request'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='MEMORY_REQUEST_MB'):
        Stage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_19_bad_cpu_request'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='CPU_REQUEST'):
        Stage(stage_name, config, path_to_stage_dir)


def test_batch_stage_input_validation(project_repo_location: Path):
    stage_name = 'stage_7_bad_batch_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='RETRIES'):
        BatchStage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_8_bad_batch_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='MAX_COMPLETION_TIME_SECONDS'):
        BatchStage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_9_bad_batch_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='MAX_COMPLETION_TIME_SECONDS'):
        BatchStage(stage_name, config, path_to_stage_dir)


def test_service_stage_input_validation(project_repo_location: Path):
    stage_name = 'stage_10_bad_service_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='REPLICAS'):
        ServiceStage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_11_bad_service_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='PORT'):
        ServiceStage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_12_bad_service_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='MAX_STARTUP_TIME_SECONDS'):
        ServiceStage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_13_bad_service_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='MAX_STARTUP_TIME_SECONDS'):
        ServiceStage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_14_bad_service_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='INGRESS'):
        ServiceStage(stage_name, config, path_to_stage_dir)

    stage_name = 'stage_15_bad_service_data'
    path_to_stage_dir = project_repo_location / stage_name
    path_to_config = path_to_stage_dir / STAGE_CONFIG_FILENAME
    config = BodyworkConfig(path_to_config)
    with raises(BodyworkStageConfigError, match='INGRESS'):
        ServiceStage(stage_name, config, path_to_stage_dir)


def test_stage_secret_parsing(project_repo_location: Path):
    path_to_stage_1_dir = project_repo_location / 'stage_1_good'
    stage_1 = stage_factory(path_to_stage_1_dir)

    path_to_stage_4_dir = project_repo_location / 'stage_4_good'
    stage_4 = stage_factory(path_to_stage_4_dir)

    assert stage_1.env_vars_from_secrets[0] == ('foobar-secret', 'FOO')
    assert stage_1.env_vars_from_secrets[1] == ('foobar-secret', 'BAR')
    assert stage_4.env_vars_from_secrets == []


def test_stage_equality_operations(project_repo_location: Path):
    path_to_stage_1_dir = project_repo_location / 'stage_1_good'
    stage_1 = stage_factory(path_to_stage_1_dir)

    path_to_stage_5_dir = project_repo_location / 'stage_5_good'
    stage_5 = stage_factory(path_to_stage_5_dir)

    assert stage_1 == stage_1
    assert stage_1 != stage_5


def test_that_requirements_can_be_installed(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_location: Path
):
    path_to_requirements = (
        project_repo_location
        / 'stage_5_good'
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
    with raises(RuntimeError, match='requirements'):
        _install_python_requirements(path_to_requirements)


def test_run_stage(
    setup_bodywork_test_project: Iterable[bool],
    project_repo_connection_string: str,
    bodywork_output_dir: Path
):
    try:
        run_stage('stage_1_good', project_repo_connection_string)
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
    with raises(BodyworkStageFailure, match='stage_3_bad_script'):
        run_stage('stage_3_bad_script', project_repo_connection_string)
