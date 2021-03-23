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
Bodywork configuration file parsing and validation.
"""
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .constants import BODYWORK_CONFIG_VERSION
from .exceptions import (
    BodyworkConfigParsingError,
    BodyworkConfigMissingSectionError,
    BodyworkConfigVersionMismatchError,
    BodyworkConfigMissingOrInvalidParamError
)


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
        :raises BodyworkConfigMissingOrInvalidParamError: if a config
            parameter is missing or has been set to an invalid value.
        """
        try:
            config_yaml = config_file_path.read_text(encoding='utf-8', errors='strict')
            config = yaml.load(config_yaml, Loader=yaml.SafeLoader)
            if type(config) is not dict:
                raise yaml.YAMLError
            self._config = config
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
            if len(config['version'].split('.')) != 2:
                raise ValueError
            if config['version'] != BODYWORK_CONFIG_VERSION:
                raise BodyworkConfigVersionMismatchError(config['version'])
        except (AttributeError, ValueError):
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
            self.stages: Dict[str, Stage] = {}
            for stage_name, stage_config in config['stages'].items():
                try:
                    if 'batch' in stage_config and 'service' in stage_config:
                        missing_or_invalid_param.append(
                            f'stages.{stage_name}.batch/service'
                        )
                        continue
                    elif 'batch' in stage_config:
                        self.stages[stage_name] = BatchStage(stage_name, stage_config)
                    elif 'service' in stage_config:
                        self.stages[stage_name] = ServiceStage(stage_name, stage_config)
                    else:
                        missing_or_invalid_param.append(
                            f'stages.{stage_name}.batch/service'
                        )
                except BodyworkConfigMissingOrInvalidParamError as e:
                    missing_or_invalid_param += e.missing_params
        except AttributeError:
            missing_or_invalid_param.append('stages._')

        if missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class Project:
    """High-level project configuration."""

    def __init__(self, config_section: Dict[str, str]):
        """Constructor.

        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """

        missing_or_invalid_param = []
        try:
            self.name = config_section['name'].lower()
        except Exception:
            missing_or_invalid_param.append('project.name')

        try:
            self.docker_image = config_section['docker_image'].lower()
        except Exception:
            missing_or_invalid_param.append('project.docker_image')

        try:
            self.DAG = config_section['DAG'].replace(' ', '')
        except Exception:
            missing_or_invalid_param.append('project.DAG')

        if missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class Logging:
    """Logging configuration."""

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
    """Common stage configuration for all stages."""

    def __init__(self, stage_name: str, config: Dict[str, Any]):
        """Constructor.

        :param stage_name: Name of stage.
        :param config: Dictionary of configuration parameters.
        """
        missing_or_invalid_param = []
        try:
            self.executable_script = config['executable_script'].strip()
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
    """Specific stage configuration for batch stages."""

    def __init__(self, stage_name: str, config: Dict[str, Any]):
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config)
        batch_config = config['batch']

        try:
            max_completion_time_seconds = int(
                batch_config['max_completion_time_seconds']
            )
            if max_completion_time_seconds < 0:
                raise ValueError
            self.max_completion_time_seconds = max_completion_time_seconds
        except Exception:
            self.missing_or_invalid_param.append(
                f'stages.{stage_name}.batch.max_completion_time_seconds'
            )

        try:
            retries = int(batch_config['retries'])
            if retries < 0:
                raise ValueError
            self.retries = retries
        except Exception:
            self.missing_or_invalid_param.append(f'stages.{stage_name}.batch.retries')

        if self.missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(self.missing_or_invalid_param)


class ServiceStage(Stage):
    """Specific stage configuration for service stages."""

    def __init__(self, stage_name, config: Dict[str, Any]):
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config)
        service_config = config['service']

        try:
            max_startup_time_seconds = int(service_config['max_startup_time_seconds'])
            if max_startup_time_seconds < 0:
                raise ValueError
            self.max_startup_time_seconds = max_startup_time_seconds
        except Exception:
            self.missing_or_invalid_param.append(
                f'stages.{stage_name}.service.max_startup_time_seconds'
            )

        try:
            replicas = int(service_config['replicas'])
            if replicas < 0:
                raise ValueError
            self.replicas = replicas
        except Exception:
            self.missing_or_invalid_param.append(f'stages.{stage_name}.service.replicas')

        try:
            port = int(service_config['port'])
            if port < 0:
                raise ValueError
            self.port = port
        except Exception:
            self.missing_or_invalid_param.append(f'stages.{stage_name}.service.port')

        try:
            if service_config['ingress'] is True or service_config['ingress'] is False:
                self.ingress = service_config['ingress']
            else:
                raise TypeError
        except Exception:
            self.missing_or_invalid_param.append(f'stages.{stage_name}.service.ingress')

        if self.missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(self.missing_or_invalid_param)
