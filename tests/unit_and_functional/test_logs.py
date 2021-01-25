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
