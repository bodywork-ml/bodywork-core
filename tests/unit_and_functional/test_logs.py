"""
Test the Bodywork custom logger.
"""
import os
from pathlib import Path

from _pytest.logging import LogCaptureFixture

from bodywork.constants import DEFAULT_LOG_LEVEL_ENV_VAR, PROJECT_CONFIG_FILENAME
from bodywork.logs import bodywork_log_factory


def test_logger_can_get_log_level_from_arg(caplog: LogCaptureFixture):
    logger = bodywork_log_factory('WARNING')
    message = 'this is a test'
    logger.warning(message)
    assert 'WARNING' in caplog.text
    assert 'bodywork' in caplog.text
    assert 'test_logs.py' in caplog.text
    assert message in caplog.text


def test_logger_can_get_log_level_from_config_file(
    project_repo_location: Path,
    caplog: LogCaptureFixture
):
    config_file_path = project_repo_location / PROJECT_CONFIG_FILENAME
    logger = bodywork_log_factory(config_file_path=config_file_path)
    message = 'this is a test'
    logger.info(message)
    assert 'INFO' in caplog.text
    assert 'bodywork' in caplog.text
    assert 'test_logs.py' in caplog.text
    assert message in caplog.text


def test_logger_can_get_log_level_from_env_var(caplog: LogCaptureFixture):
    os.environ[DEFAULT_LOG_LEVEL_ENV_VAR] = 'DEBUG'
    logger = bodywork_log_factory()
    message = 'this is a test'
    logger.debug(message)
    assert 'DEBUG' in caplog.text
    assert 'bodywork' in caplog.text
    assert 'test_logs.py' in caplog.text
    assert message in caplog.text


def test_logger_can_get_default_log_level(caplog: LogCaptureFixture):
    logger = bodywork_log_factory()
    message = 'this is a test'
    logger.info(message)
    assert 'INFO' in caplog.text
    assert 'bodywork' in caplog.text
    assert 'test_logs.py' in caplog.text
    assert message in caplog.text
