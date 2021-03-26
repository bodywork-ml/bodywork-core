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
from typing import Any, Dict, Iterable, List, Sequence

import yaml

from .constants import BODYWORK_CONFIG_VERSION
from .exceptions import (
    BodyworkConfigParsingError,
    BodyworkConfigMissingSectionError,
    BodyworkConfigVersionMismatchError,
    BodyworkConfigMissingOrInvalidParamError
)

DAG = Iterable[Iterable[str]]


class BodyworkConfig:
    """Configuration data that has been parsed and validated."""

    def __init__(self, config_file_path: Path, check_py_modules_exist: bool = False):
        """Constructor.

        :param config_file_path: Config file path.
        :param check_py_modules_exist: Whether to check that the
            executable Python modules specified in stage configs, exist.
        :raises FileExistsError: if config_file_path does not exist.
        :raises BodyworkConfigParsingError: if config file cannot be
            parsed as valid YAML.
        """
        try:
            config_yaml = config_file_path.read_text(encoding='utf-8', errors='strict')
            config = yaml.load(config_yaml, Loader=yaml.SafeLoader)
            if type(config) is not dict:
                raise yaml.YAMLError
            self._config = config
            self._config_file_path = config_file_path
            self._root_dir = config_file_path.parent
        except (FileNotFoundError, IsADirectoryError):
            raise FileExistsError(f'no config file found at {config_file_path}')
        except yaml.YAMLError as e:
            raise BodyworkConfigParsingError(config_file_path) from e
        self.check_py_modules_exist = check_py_modules_exist
        self._validate_parsed_config()

    def _validate_parsed_config(self) -> None:
        """Validate configuration parameters.

        This function exists seperately to the class constructor purely
        to facilitate easier testing.

        :raises BodyworkConfigMissingSectionError: if config file does
            not contain all of the following sections: version,
            project, stages and logging.
        :raises BodyworkConfigVersionMismatchError: if config file
            schema version does not match the schame version supported
            by the current Bodywork version.
        :raises BodyworkConfigMissingOrInvalidParamError: if a config
            parameter is missing or has been set to an invalid value.
        """
        config = self._config
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
            self.project = ProjectConfig(config['project'])
        except BodyworkConfigMissingOrInvalidParamError as e:
            missing_or_invalid_param += e.missing_params

        try:
            self.logging = LoggingConfig(config['logging'])
        except BodyworkConfigMissingOrInvalidParamError as e:
            missing_or_invalid_param += e.missing_params

        try:
            self.stages: Dict[str, StageConfig] = {}
            for stage_name, stage_config in config['stages'].items():
                if 'batch' in stage_config and 'service' in stage_config:
                    missing_or_invalid_param.append(
                        f'stages.{stage_name}.batch/service'
                    )
                    continue
                elif 'batch' in stage_config:
                    self.stages[stage_name] = BatchStageConfig(
                        str(stage_name),
                        stage_config,
                        self._root_dir
                    )
                elif 'service' in stage_config:
                    self.stages[stage_name] = ServiceStageConfig(
                        str(stage_name),
                        stage_config,
                        self._root_dir
                    )
                else:
                    missing_or_invalid_param.append(
                        f'stages.{stage_name}.batch/service'
                    )
        except AttributeError:
            missing_or_invalid_param.append('stages._ - no stage configs provided')

        stages_in_workflow_without_valid_config = _check_workflow_stages_are_configured(
            self.project.workflow,
            self.stages.keys()
        )
        missing_or_invalid_param += stages_in_workflow_without_valid_config

        if self.check_py_modules_exist:
            for stage_name, stage in self.stages.items():
                if not stage.executable_module_path.exists():
                    missing_or_invalid_param.append(
                        f'stages.{stage_name}.executable_module_path -> does not exist'
                    )

        if missing_or_invalid_param:
            missing_or_invalid_param.sort()
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class ProjectConfig:
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
            self.workflow = _parse_dag_definition(self.DAG)
        except ValueError as e:
            missing_or_invalid_param.append(f'project.DAG -> {e}')
        except Exception:
            missing_or_invalid_param.append('project.DAG')

        if missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class LoggingConfig:
    """Logging configuration."""

    def __init__(self, config_section: Dict[str, str]):
        """Constructor.

        :param config: Dictionary of configuration parameters.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """

        missing_or_invalid_param = []
        try:
            self.log_level = str(config_section['log_level'])
        except Exception:
            missing_or_invalid_param.append('logging.log_level')

        if missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(missing_or_invalid_param)


class StageConfig:
    """Common stage configuration for all stages."""

    def __init__(self, stage_name: str, config: Dict[str, Any], root_dir: Path):
        """Constructor.

        :param stage_name: Name of stage.
        :param config: Dictionary of configuration parameters.
        :param root_dir: The root directory of the project containing
            the bodywork config file and the stage directories.
        """
        self.name = stage_name
        missing_or_invalid_param = []

        try:
            self.executable_module_path = root_dir / config['executable_module_path']
            self.executable_module = self.executable_module_path.name
        except Exception:
            missing_or_invalid_param.append(
                f'stages.{stage_name}.executable_module_path'
            )

        if 'args' in config:
            try:
                if any(e is None for e in config['args']):
                    missing_or_invalid_param.append(f'stages.{stage_name}.args')
                else:
                    self.args = [str(arg) for arg in config['args']]
            except Exception:
                missing_or_invalid_param.append(f'stages.{stage_name}.args')
        else:
            self.args = []

        try:
            self.cpu_request = float(config['cpu_request'])
        except Exception:
            missing_or_invalid_param.append(f'stages.{stage_name}.cpu_request')

        try:
            self.memory_request = int(config['memory_request_mb'])
        except Exception:
            missing_or_invalid_param.append(f'stages.{stage_name}.memory_request_mb')

        if 'requirements' in config:
            try:
                if any(e is None for e in config['requirements']):
                    missing_or_invalid_param.append(f'stages.{stage_name}.requirements')
                elif any(str(e) for e in config['requirements']):
                    self.requirements = config['requirements']
            except Exception:
                missing_or_invalid_param.append(f'stages.{stage_name}.requirements')
        else:
            self.requirements = []

        if 'secrets' in config:
            try:
                self.env_vars_from_secrets = [
                    (secret_name.lower(), secret_key.upper())
                    for secret_key, secret_name in config['secrets'].items()
                ]
            except Exception:
                missing_or_invalid_param.append(f'stages.{stage_name}.secrets')
        else:
            self.env_vars_from_secrets = []

        self._missing_or_invalid_param = missing_or_invalid_param

    def __eq__(self, other) -> bool:
        """Object equality operator.

        :param other: Other Stage object to compare this one too.
        """
        if self.name == other.name:
            return True
        else:
            return False


class BatchStageConfig(StageConfig):
    """Specific stage configuration for batch stages."""

    def __init__(self, stage_name: str, config: Dict[str, Any], root_dir: Path):
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :param root_dir: The root directory of the project containing
            the bodywork config file and the stage directories.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config, root_dir)
        batch_config = config['batch']

        try:
            max_completion_time = int(batch_config['max_completion_time_seconds'])
            if max_completion_time < 0:
                raise ValueError
            self.max_completion_time = max_completion_time
        except Exception:
            self._missing_or_invalid_param.append(
                f'stages.{stage_name}.batch.max_completion_time_seconds'
            )

        try:
            retries = int(batch_config['retries'])
            if retries < 0:
                raise ValueError
            self.retries = retries
        except Exception:
            self._missing_or_invalid_param.append(f'stages.{stage_name}.batch.retries')

        if self._missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(self._missing_or_invalid_param)  # noqa


class ServiceStageConfig(StageConfig):
    """Specific stage configuration for service stages."""

    def __init__(self, stage_name, config: Dict[str, Any], root_dir: Path):
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :param root_dir: The root directory of the project containing
            the bodywork config file and the stage directories.
        :raises BodyworkConfigMissingOrInvalidParamError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config, root_dir)
        service_config = config['service']

        try:
            max_startup_time = int(service_config['max_startup_time_seconds'])
            if max_startup_time < 0:
                raise ValueError
            self.max_startup_time = max_startup_time
        except Exception:
            self._missing_or_invalid_param.append(
                f'stages.{stage_name}.service.max_startup_time_seconds'
            )

        try:
            replicas = int(service_config['replicas'])
            if replicas < 0:
                raise ValueError
            self.replicas = replicas
        except Exception:
            self._missing_or_invalid_param.append(
                f'stages.{stage_name}.service.replicas'
            )

        try:
            port = int(service_config['port'])
            if port < 0:
                raise ValueError
            self.port = port
        except Exception:
            self._missing_or_invalid_param.append(f'stages.{stage_name}.service.port')

        try:
            if service_config['ingress'] is True or service_config['ingress'] is False:
                self.create_ingress = service_config['ingress']
            else:
                raise TypeError
        except Exception:
            self._missing_or_invalid_param.append(f'stages.{stage_name}.service.ingress')

        if self._missing_or_invalid_param:
            raise BodyworkConfigMissingOrInvalidParamError(self._missing_or_invalid_param)  # noqa


def _parse_dag_definition(dag_definition: str) -> DAG:
    """Parse DAG definition string.

    :param dag_definition: A DAG definition in string format.
    :raises ValueError: If any 'null' (zero character) stage names are
        found.
    :return: A list of steps, where each step is a list of Bodywork
        project stage names (containing a list of stages to run in each
        step).
    """
    steps = dag_definition.replace(' ', '').split('>>')
    stages_in_steps = [step.split(',') for step in steps]
    steps_with_null_stages = [
        str(n)
        for n, step in enumerate(stages_in_steps, start=1) for stage in step
        if stage == ''
    ]
    if len(steps_with_null_stages) > 0:
        msg = (f'null stages found in step {", ".join(steps_with_null_stages)} when '
               f'parsing DAG definition')
        raise ValueError(msg)
    return stages_in_steps


def _check_workflow_stages_are_configured(
    workflow: Iterable[Iterable[str]],
    stages: Iterable[str]
) -> Sequence[str]:
    """Identify stages in workflow that have not been configured.

    :param workflow: A project DAG parsed into a Bodywork workflow.
    :param stages: List of stages that have been configured.
    :return: List of missing stage messages.
    """
    stages_in_workflow = [stage for step in workflow for stage in step]
    missing_stages = [
        f'project.workflow - cannot find valid stage @ stages.{stage}'
        for stage in stages_in_workflow
        if stage not in stages
    ]
    return missing_stages
