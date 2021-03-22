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
Test Bodywork config reading, parsing and validation.
"""
from pathlib import Path

from pytest import raises

from bodywork.config import BodyworkConfig, ProjectConfig, LoggingConfig
from bodywork.constants import PROJECT_CONFIG_FILENAME
from bodywork.exceptions import (
    BodyworkConfigMissingSectionError,
    BodyworkConfigVersionMismatchError,
    BodyworkConfigMissingOrInvalidParametersError,
    BodyworkConfigParsingError,
    BodyworkMissingConfigError
)


def test_that_invalid_config_file_path_raises_error():
    bad_config_file = Path('./tests/not_a_real_directory/bodywerk.ini')
    with raises(FileExistsError, match='no config file found'):
        BodyworkConfig(bad_config_file)


def test_that_invalid_config_format_raises_error():
    config_file = Path('./tests/resources/project_repo/bodywork.ini')
    expected_exception_msg = f'cannot parse YAML from {config_file}'
    with raises(BodyworkConfigParsingError, match=expected_exception_msg):
        BodyworkConfig(config_file)


def test_that_empty_config_file_raises_error():
    config_file = Path('./tests/resources/project_repo/bodywork_empty.yaml')
    expected_exception_msg = f'cannot parse YAML from {config_file}'
    with raises(BodyworkConfigParsingError, match=expected_exception_msg):
        BodyworkConfig(config_file)


def test_that_config_file_with_missing_sections_raises_error():
    config_file = Path('./tests/resources/project_repo/bodywork_missing_sections.yaml')
    expected_exception_msg = f'missing sections: version, project, stages, logging'
    with raises(BodyworkConfigMissingSectionError, match=expected_exception_msg):
        BodyworkConfig(config_file)


def test_bodywork_config_project_section_validation(
    project_repo_location: Path
):
    missing_all_params = {'not_a_valid_section': None}
    expected_msg = (f'missing parameters from project section: '
                    f'name, docker_image, DAG')
    with raises(BodyworkConfigMissingOrInvalidParametersError, match=expected_msg):
        ProjectConfig(missing_all_params)

    has_all_params = {'name': 'foo', 'docker_image': 'me/my-image:latest', 'DAG': 'a>>b'}
    try:
        ProjectConfig(has_all_params)
        assert True
    except:
        assert False


def test_bodywork_config_logging_section_validation(
    project_repo_location: Path
):
    missing_all_params = {'not_a_valid_section': None}
    expected_msg = f'missing parameters from logging section: log_level'
    with raises(BodyworkConfigMissingOrInvalidParametersError, match=expected_msg):
        LoggingConfig(missing_all_params)

    has_all_params = {'log_level': 'INFO'}
    try:
        LoggingConfig(has_all_params)
        assert True
    except:
        assert False


def test_that_config_values_can_be_retreived_from_valid_config(
    project_repo_location: Path
):
    config_file = project_repo_location / PROJECT_CONFIG_FILENAME
    config = BodyworkConfig(config_file)
    assert config.project.name == 'bodywork-test-project'
    assert config.logging.log_level == 'info'
    assert len(config.stages) == 3
    assert 'stage_1_good' in config.stages
    assert 'batch' in config.stages['stage_1_good']
    assert config.stages['stage_1_good']['executable_script'] == 'main.py'
    assert config.stages['stage_1_good']['batch']['retries'] == 4
    assert config.stages['stage_1_good']['secrets']['FOO'] == 'foobar-secret'
    assert (config.stages['stage_1_good']['requirements']
            == ['boto3==1.16.15', 'joblib==0.17.0'])
