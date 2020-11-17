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
