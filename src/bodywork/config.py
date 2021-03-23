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
from typing import Any, Dict, List, Sequence, Union

import yaml

from .constants import BODYWORK_CONFIG_VERSION
from .exceptions import (
    BodyworkConfigParsingError,
    BodyworkConfigMissingSectionError,
    BodyworkConfigVersionMismatchError,
    BodyworkMissingConfigError,
    BodyworkConfigMissingOrInvalidParamError
)

ConfigValues = Union[str, int, float, bool]
ConfigStage = Dict[str, Union[ConfigValues, Dict[str, ConfigValues], Sequence[str]]]


class BodyworkConfig:
    """Configuration data that has been parsed and validated."""

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
        if 'project' not in config:
            missing_config_sections.append('project')
        if 'stages' not in config:
            missing_config_sections.append('stages')
        if 'logging' not in config:
            missing_config_sections.append('logging')
        if missing_config_sections:
            raise BodyworkConfigMissingSectionError(missing_config_sections)

        try:
            if str(config['version']) != BODYWORK_CONFIG_VERSION:
                raise BodyworkConfigVersionMismatchError(config['version'])
        except Exception:
            raise BodyworkConfigMissingOrInvalidParamError(['version'])

        missing_or_invalid_param: List[str] = []
        try:
            self.project = Project(config['project'])
        except BodyworkConfigMissingOrInvalidParamError as e:
            missing_or_invalid_param += e.missing_params

        try:
            self.logging = Logging(config['logging'])
        except BodyworkConfigMissingOrInvalidParamError as e:
            missing_or_invalid_param += e.missing_params

        try:
            self.stages: Sequence[Stage] = []
            for stage_name, stage_config in config['stages'].items():
                try:
                    if (not ('batch' in stage_config or 'service' in stage_config)
                            or ('batch' in stage_config and 'service' in stage_config)):
                        missing_or_invalid_param.append(
                            f'stages.{stage_name}.batch/service'
                        )
                        continue
                    self.stages.append(Stage(stage_name, stage_config))
                except BodyworkConfigMissingOrInvalidParamError as e:
                    missing_or_invalid_param += e.missing_params
        except TypeError:
            missing_or_invalid_param.append('stages._')

        if missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class Project:
    """Class for project section of Bodywork config."""

    def __init__(self, config_section: Dict[str, str]):
        """Constructor.

        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """

        missing_or_invalid_param = []
        try:
            self.name = str(config_section['name']).lower()
        except Exception:
            missing_or_invalid_param.append('project.name')

        try:
            self.docker_image = str(config_section['docker_image']).lower()
        except Exception:
            missing_or_invalid_param.append('project.docker_image')

        try:
            self.DAG = str(config_section['DAG'])
        except Exception:
            missing_or_invalid_param.append('project.DAG')

        if missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class Logging:
    """Class for logging section of Bodywork config."""

    def __init__(self, config_section: Dict[str, str]):
        """Constructor.

        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """

        missing_or_invalid_param = []
        try:
            self.log_level = str(config_section['log_level']).lower()
        except Exception:
            missing_or_invalid_param.append('logging.log_level')

        if missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class Stage:
    """Common stage data in stages section of Bodywork config."""

    def __init__(self, stage_name: str, config: Dict[str, Any]):
        """Constructor.

        :param stage_name: Name of stage.
        :param config: Dictionary of configuration parameters.
        """
        missing_or_invalid_param = []
        try:
            self.executable_script = str(config['executable_script'])
        except Exception:
            missing_or_invalid_param.append(f'stages.{stage_name}.executable_script')

        try:
            self.cpu_request = float(config['cpu_request'])
        except Exception:
            missing_or_invalid_param.append(f'stages.{stage_name}.cpu_request')

        try:
            self.memory_request_mb = float(config['memory_request_mb'])
        except Exception:
            missing_or_invalid_param.append(f'stages.{stage_name}.memory_request_mb')

        if 'requirements' in config:
            try:
                if any(str(e) for e in config['requirements'] if e is not None):
                    self.requirements = config['requirements']
                else:
                    self.requirements = []
            except Exception:
                missing_or_invalid_param.append(f'stages.{stage_name}.requirements')
        else:
            self.requirements = []

        if 'secrets' in config:
            try:
                if any(str(v) for k, v in config['secrets'].items() if v is not None):
                    self.secrets = config['secrets']
                else:
                    self.secrets = {}
            except Exception:
                missing_or_invalid_param.append(f'stages.{stage_name}.secrets')
        else:
            self.secrets = {}

        self.missing_or_invalid_param = missing_or_invalid_param


class BatchStage(Stage):
    """Batch stage data within stages section of Bodywork config."""

    def __init__(self, stage_name: str, config: Dict[str, ConfigValues]):
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config)

        try:
            self.max_completion_time_seconds = int(config['max_completion_time_seconds'])
        except Exception:
            self.missing_or_invalid_param.append(
                f'stage.{stage_name}.max_completion_time_seconds'
            )

        try:
            self.retries = int(config['retries'])
        except Exception:
            self.missing_or_invalid_param.append(f'stage.{stage_name}.batch.retries')

        if self.missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(self.missing_or_invalid_param)


class ServiceStage(Stage):
    """Service stage data within stages section of Bodywork config."""

    def __init__(self, stage_name, config: Dict[str, ConfigValues]):
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config)

        try:
            self.max_startup_time_seconds = int(config['max_startup_time_seconds'])
        except Exception:
            self.missing_or_invalid_param.append(
                f'stages.{stage_name}.service.max_startup_time_seconds'
            )

        try:
            self.replicas = int(config['replicas'])
        except Exception:
            self.missing_or_invalid_param.append(f'stages.{stage_name}.service.replicas')

        try:
            self.port = int(config['port'])
        except Exception:
            self.missing_or_invalid_param.append(f'stages.{stage_name}.service.port')

        try:
            if config['ingress'] is True or config['ingress'] is False:
                self.ingress = config['ingress']
            else:
                raise TypeError
        except Exception:
            self.missing_or_invalid_param.append(f'stages.{stage_name}.service.ingress')

        if self.missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(self.missing_or_invalid_param)
