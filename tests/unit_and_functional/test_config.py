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
Test the Bodywork config handling.
"""
from pathlib import Path

from pytest import raises

from bodywork.config import BodyworkConfig
from bodywork.constants import PROJECT_CONFIG_FILENAME
from bodywork.exceptions import BodyworkProjectConfigYAMLError


def test_that_invalid_config_file_path_raises_error():
    bad_config_file_path = Path('./tests/not_a_real_directory/bodywerk.ini')
    with raises(FileExistsError, match='no config file found'):
        BodyworkConfig(bad_config_file_path)


def test_that_invalid_config_format_raises_error():
    config_file_path = Path('./tests/resources/project_repo/bodywork.ini')
    expected_exception_msg = f'cannot parse YAML from {config_file_path}'
    with raises(BodyworkProjectConfigYAMLError, match=expected_exception_msg):
        BodyworkConfig(config_file_path)


def test_that_config_values_can_be_retreived_from_valid_config(
    project_repo_location: Path
):
    config_file_path = project_repo_location / PROJECT_CONFIG_FILENAME
    config = BodyworkConfig(config_file_path)
    assert config['project']['name'] == 'bodywork-test-project'
    assert config['logging']['log_level'] == 'INFO'
    assert len(config['stages']) == 3
    assert 'stage_1_good' in config['stages']
    assert 'batch' in config['stages']['stage_1_good']
    assert config['stages']['stage_1_good']['executable_script'] == 'main.py'
    assert config['stages']['stage_1_good']['batch']['retries'] == 4
    assert config['stages']['stage_1_good']['secrets']['FOO'] == 'foobar-secret'
    assert (config['stages']['stage_1_good']['requirements']
            == ['boto3==1.16.15', 'joblib==0.17.0'])
