# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020  Bodywork Machine Learning Ltd.

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


def test_that_invalid_config_file_path_raises_error():
    bad_config_file_path = Path('./tests/not_a_real_directory/bodywerk.ini')
    with raises(FileExistsError, match='no config file found'):
        BodyworkConfig(bad_config_file_path)


def test_that_invalid_config_requests_raise_error(
    project_repo_location: Path
):
    config_file_path = project_repo_location / PROJECT_CONFIG_FILENAME
    config = BodyworkConfig(config_file_path)
    with raises(KeyError, match='not_a_real_config_section'):
        config['not_a_real_config_section']
    with raises(KeyError, match='not_a_real_parameter'):
        config['default']['not_a_real_parameter']


def test_that_config_values_can_be_retreived(
    project_repo_location: Path
):
    config_file_path = project_repo_location / PROJECT_CONFIG_FILENAME
    config = BodyworkConfig(config_file_path)
    assert config['default']['PROJECT_NAME'] == 'bodywork-test-project'
    assert config['logging']['LOG_LEVEL'] == 'INFO'
