"""
Custom logger for use accross all Bodywork modules.
"""
import os
import sys
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    Formatter,
    getLogger,
    INFO,
    Logger,
    StreamHandler,
    WARNING
)
from pathlib import Path
from typing import Optional

from .config import BodyworkConfig
from .constants import (
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_LEVEL_ENV_VAR,
    DEFAULT_PROJECT_DIR,
    PROJECT_CONFIG_FILENAME
)


def bodywork_log_factory(
    log_level: Optional[str] = None,
    config_file_path: Path = DEFAULT_PROJECT_DIR / PROJECT_CONFIG_FILENAME
) -> Logger:
    """Create a standardised Bodywork logger.

    If a log level is specified as an argument, then it will take
    precedence overall all other methods of setting the log-level. Next
    in the waterfall of priority is the log-level set in the project
    config file, and then after that the level set by the
    BODYWORK_LOG_LEVEL environment variable. Failing that, the default
    log level (INFO) will be used.

    :param log_level: The minimum severity level of messages to log,
        defaults to None.
    :param config_file_path: Path to project config file, defaults
        DEFAULT_PROJECT_DIR/PROJECT_CONFIG_FILENAME.
    """
    log_level_mapping = {
        'DEBUG': DEBUG,
        'INFO': INFO,
        'WARNING': WARNING,
        'ERROR': ERROR,
        'CRITICAL': CRITICAL
    }
    log = getLogger("bodywork")
    if log_level is not None:
        log.setLevel(log_level_mapping[log_level])
    else:
        try:
            bodywork_config = BodyworkConfig(config_file_path)
            log.setLevel(bodywork_config['logging']['LOG_LEVEL'])
        except FileExistsError:
            try:
                log_level_from_env_var = os.environ[DEFAULT_LOG_LEVEL_ENV_VAR]
                log.setLevel(log_level_mapping[log_level_from_env_var])
            except KeyError:
                log.setLevel(log_level_mapping[DEFAULT_LOG_LEVEL])
    if not log.hasHandlers():
        log_handler = StreamHandler(sys.stdout)
        log_formatter = Formatter(
            '%(asctime)s - '
            '%(levelname)s - '
            '%(module)s.%(funcName)s - '
            '%(message)s'
        )
        log_handler.setFormatter(log_formatter)
        log.addHandler(log_handler)
    return log
