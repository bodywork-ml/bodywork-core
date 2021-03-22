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
Bodywork config file reader and parser.
"""
from pathlib import Path
from typing import Dict, Sequence, Union

import yaml

from .constants import BODYWORK_CONFIG_VERSION
from .exceptions import (
    BodyworkConfigMissingSectionError,
    BodyworkConfigVersionMismatchError,
    BodyworkConfigParsingError,
    BodyworkMissingConfigError
)

SectionConfig = Dict[str, str]
StageConfig = Dict[str, Union[str, int, float, Dict[str, Union[str, int, float, bool]]]]


class BodyworkConfig:
    """Config file handler."""

    def __init__(self, config_file_path: Path):
        """Constructor.

        :param config_file_path: Config file path.
        :raises FileExistsError: if config_file_path does not exist.
        :raises BodyworkConfigParsingError: if config file cannot be
            parsed as valid YAML.
        :raises BodyworkConfigMissingSectionError: if config file does
            not contain all of the following sections: version,
            project, stages and logging.
        :raises BodyworkConfigVersionMismatchError: if config file
            schema version does not match the schame version supported
            by the current Bodywork version.
        """
        try:
            config_yaml =  config_file_path.read_text(encoding='utf-8', errors='strict')
            config = yaml.load(config_yaml, Loader=yaml.SafeLoader)
            if type(config) is not dict:
               raise yaml.YAMLError 
            self._config =  config
        except (FileNotFoundError, IsADirectoryError):
            raise FileExistsError(f'no config file found at {config_file_path}')
        except yaml.YAMLError as e:
            raise BodyworkConfigParsingError(config_file_path) from e

        missing_config_sections = []
        if 'version' not in config:
            missing_config_sections.append('version')
        
        if 'project' in config:
            self.project: SectionConfig = config['project']
        else:
            missing_config_sections.append('project')

        if 'stages' in config:
            self.stages: Sequence[SectionConfig] = config['stages']
        else:
            missing_config_sections.append('stages')

        if 'logging' in config:
            self.logging: SectionConfig = config['logging']
        else:
            missing_config_sections.append('logging')

        if missing_config_sections:
            raise BodyworkConfigMissingSectionError(missing_config_sections)

        if type(config['version']) != str:
            raise BodyworkMissingConfigError('version')
        if config['version'] != BODYWORK_CONFIG_VERSION:
            raise BodyworkConfigVersionMismatchError(config['version'])
