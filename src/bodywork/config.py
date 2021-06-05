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
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import cerberus
import yaml

from .constants import BODYWORK_CONFIG_VERSION
from .exceptions import (
    BodyworkConfigParsingError,
    BodyworkConfigMissingSectionError,
    BodyworkConfigVersionMismatchError,
    BodyworkConfigValidationError,
)

DAG = Iterable[Iterable[str]]
VALID_K8S_NAME_REGEX = r"[a-zA-Z0-9-\.]+"


class DictDataValidator:
    """Data validator for dictionaries.

    This class is designed to validate key-value data against a schema.
    It uses Cerberus - https://docs.python-cerberus.org/en/stable/ - and
    its in-built schema definition language.
    """

    def __init__(self, schema: Dict[str, Dict[str, Any]]):
        """Constructor.

        :param schema: Valid Cerberus data schema.
        """
        self._data_validator = cerberus.Validator(schema=schema, allow_unknown=True)

    def find_errors_in(self, data: Dict[str, Any], prefix: str = "") -> List[str]:
        """Find schema invalidation errors.

        :param data: Data to validate against the schema.
        :param prefix: Prefix to add to all data keys that map to an
            error, defaults to ''.
        :return: List of data validation errors.
        """
        is_valid = self._data_validator.validate(data)
        if is_valid:
            return []
        else:
            errors = self._data_validator.errors
            return self._format_errors(errors, prefix)

    @staticmethod
    def _format_errors(errors: Dict[str, Any], prefix: str = "") -> List[str]:
        """Generate human-readable error messages.

        :param errors: Raw error output from data validation.
        :param prefix: Prefix to add to all data keys that map to an
            error, defaults to ''.
        :return: List of formatted errors.
        """

        def format_error(k: str, v: Any) -> str:
            try:
                err_msg = f'{prefix}{k} -> {", ".join(v)}'
            except TypeError:
                err_msg = f"{prefix}{k} -> {json.dumps(v)}"
            return err_msg

        return [format_error(k, v) for k, v in errors.items()]


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
            config_yaml = config_file_path.read_text(encoding="utf-8", errors="strict")
            config = yaml.load(config_yaml, Loader=yaml.SafeLoader)
            if type(config) is not dict:
                raise yaml.YAMLError
            self._config = config
            self._config_file_path = config_file_path
            self._root_dir = config_file_path.parent
        except (FileNotFoundError, IsADirectoryError):
            raise FileExistsError(f"no config file found at {config_file_path}")
        except yaml.YAMLError as e:
            raise BodyworkConfigParsingError(config_file_path) from e
        self.check_py_modules_exist = check_py_modules_exist
        self._validate_parsed_config()

    def _validate_parsed_config(self) -> None:
        """Validate configuration parameters.

        This function exists separately to the class constructor purely
        to facilitate easier testing.

        :raises BodyworkConfigMissingSectionError: if config file does
            not contain all of the following sections: version,
            project, stages and logging.
        :raises BodyworkConfigVersionMismatchError: if config file
            schema version does not match the schema version supported
            by the current Bodywork version.
        :raises BodyworkConfigValidationError: if a config
            parameter is missing or has been set to an invalid value.
        """
        config = self._config
        missing_config_sections = []
        if "version" not in config:
            missing_config_sections.append("version")
        if "project" not in config:
            missing_config_sections.append("project")
        if "stages" not in config:
            missing_config_sections.append("stages")
        if "logging" not in config:
            missing_config_sections.append("logging")
        if missing_config_sections:
            raise BodyworkConfigMissingSectionError(missing_config_sections)

        try:
            if len(config["version"].split(".")) != 2:
                raise ValueError
            if config["version"] != BODYWORK_CONFIG_VERSION:
                raise BodyworkConfigVersionMismatchError(config["version"])
        except (AttributeError, ValueError):
            raise BodyworkConfigValidationError(["version"])

        missing_or_invalid_param: List[str] = []
        try:
            self.project = ProjectConfig(config["project"])
        except BodyworkConfigValidationError as e:
            missing_or_invalid_param += e.missing_params

        try:
            self.logging = LoggingConfig(config["logging"])
        except BodyworkConfigValidationError as e:
            missing_or_invalid_param += e.missing_params

        try:
            self.stages: Dict[str, StageConfig] = {}
            for stage_name, stage_config in config["stages"].items():
                if "batch" in stage_config and "service" in stage_config:
                    missing_or_invalid_param.append(
                        f"stages.{stage_name}.batch/service"
                    )
                    continue
                elif "batch" in stage_config:
                    self.stages[stage_name] = BatchStageConfig(
                        str(stage_name), stage_config, self._root_dir
                    )
                elif "service" in stage_config:
                    self.stages[stage_name] = ServiceStageConfig(
                        str(stage_name), stage_config, self._root_dir
                    )
                else:
                    missing_or_invalid_param.append(
                        f"stages.{stage_name}.batch/service"
                    )
        except AttributeError:
            missing_or_invalid_param.append("stages._ - no stage configs provided")

        stages_in_workflow_without_valid_config = _check_workflow_stages_are_configured(
            self.project.workflow, self.stages.keys()
        )
        missing_or_invalid_param += stages_in_workflow_without_valid_config
        if self.project.run_on_failure:
            if self.project.run_on_failure not in self.stages.keys():
                missing_or_invalid_param.append(
                    f"project.run_on_failure -> cannot find valid stage: "
                    f"{self.project.run_on_failure} to run on workflow failure."
                )
        if self.check_py_modules_exist:
            for stage_name, stage in self.stages.items():
                if not stage.executable_module_path.exists():
                    missing_or_invalid_param.append(
                        f"stages.{stage_name}.executable_module_path -> does not exist"
                    )

        if missing_or_invalid_param:
            missing_or_invalid_param.sort()
            raise BodyworkConfigValidationError(missing_or_invalid_param)


class ProjectConfig:
    """High-level project configuration."""

    SCHEMA = {
        "name": {"type": "string", "required": True, "regex": VALID_K8S_NAME_REGEX},
        "docker_image": {"type": "string", "required": True},
        "DAG": {"type": "string", "required": True},
        "usage_stats": {"type": "boolean", "required": False},
        "run_on_failure": {"type": "string", "required": False},
    }

    def __init__(self, config_section: Dict[str, str]):
        """Constructor.

        :param config_section: Dictionary of configuration parameters.
        :raises BodyworkConfigValidationError: if any
            required configuration parameters are missing or invalid.
        """

        data_validator = DictDataValidator(self.SCHEMA)
        missing_or_invalid_param = data_validator.find_errors_in(
            config_section, prefix="project."
        )
        if missing_or_invalid_param:
            raise BodyworkConfigValidationError(missing_or_invalid_param)
        else:
            self.name = config_section["name"]
            self.docker_image = config_section["docker_image"]
            self.DAG = config_section["DAG"]
            self.usage_stats = (
                config_section["usage_stats"]
                if "usage_stats" in config_section
                else True
            )
            self.run_on_failure = (
                config_section["run_on_failure"]
                if "run_on_failure" in config_section
                else ""
            )
            try:
                self.workflow = _parse_dag_definition(config_section["DAG"])
            except ValueError as e:
                raise BodyworkConfigValidationError([f"project.DAG -> {e}"])


class LoggingConfig:
    """Logging configuration."""

    SCHEMA = {
        "log_level": {
            "type": "string",
            "required": True,
            "allowed": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        }
    }

    def __init__(self, config_section: Dict[str, str]):
        """Constructor.

        :param config_section: Dictionary of configuration parameters.
        :raises BodyworkConfigValidationError: if any
            required configuration parameters are missing or invalid.
        """

        data_validator = DictDataValidator(self.SCHEMA)
        missing_or_invalid_param = data_validator.find_errors_in(
            config_section, prefix="logging."
        )
        if missing_or_invalid_param:
            raise BodyworkConfigValidationError(missing_or_invalid_param)
        else:
            self.log_level = config_section["log_level"]


class StageConfig:
    """Common stage configuration for all stages."""

    SCHEMA_GENERIC = {
        "executable_module_path": {
            "type": "string",
            "required": True,
            "regex": r".+(\.py$)",
        },
        "args": {"type": "list", "required": False, "schema": {"type": "string"}},
        "cpu_request": {"type": "float", "required": True, "min": 0.0},
        "memory_request_mb": {"type": "integer", "required": True, "min": 0},
        "requirements": {
            "type": "list",
            "required": False,
            "schema": {"type": "string"},
        },
        "secrets": {
            "type": "dict",
            "required": False,
            "keysrules": {"type": "string"},
            "valuesrules": {"type": "string", "regex": VALID_K8S_NAME_REGEX},
        },
    }

    def __init__(self, stage_name: str, config: Dict[str, Any], root_dir: Path):
        """Constructor.

        :param stage_name: Name of stage.
        :param config: Dictionary of configuration parameters.
        :param root_dir: The root directory of the project containing
            the bodywork config file and the stage directories.
        """
        data_validator = DictDataValidator(self.SCHEMA_GENERIC)
        self._missing_or_invalid_param = data_validator.find_errors_in(
            config, prefix=f"stages.{stage_name}."
        )
        if not self._missing_or_invalid_param:
            self.name = stage_name
            self.executable_module_path = root_dir / config["executable_module_path"]
            self.executable_module = self.executable_module_path.name
            self.args = config["args"] if "args" in config else []
            self.cpu_request = config["cpu_request"]
            self.memory_request = config["memory_request_mb"]
            self.requirements = (
                config["requirements"] if "requirements" in config else []
            )
            if "secrets" in config:
                self.env_vars_from_secrets = [
                    (secret_name, secret_key)
                    for secret_key, secret_name in config["secrets"].items()
                ]
            else:
                self.env_vars_from_secrets = []

    def __eq__(self, other: Any) -> bool:
        """Object equality operator.

        :param other: Other Stage object to compare this one too.
        """
        if self.name == other.name:
            return True
        else:
            return False


class BatchStageConfig(StageConfig):
    """Specific stage configuration for batch stages."""

    SCHEMA_BATCH = {
        "max_completion_time_seconds": {"type": "integer", "required": True, "min": 0},
        "retries": {"type": "integer", "required": True, "min": 0},
    }

    def __init__(self, stage_name: str, config: Dict[str, Any], root_dir: Path):
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :param root_dir: The root directory of the project containing
            the bodywork config file and the stage directories.
        :raises BodyworkConfigValidationError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config, root_dir)
        batch_config = config["batch"]
        data_validator = DictDataValidator(self.SCHEMA_BATCH)
        self._missing_or_invalid_param += data_validator.find_errors_in(
            batch_config, prefix=f"stages.{stage_name}.batch."
        )
        if not self._missing_or_invalid_param:
            self.max_completion_time = batch_config["max_completion_time_seconds"]
            self.retries = batch_config["retries"]
        else:
            raise BodyworkConfigValidationError(self._missing_or_invalid_param)


class ServiceStageConfig(StageConfig):
    """Specific stage configuration for service stages."""

    SCHEMA_SERVICE = {
        "max_startup_time_seconds": {"type": "integer", "required": True, "min": 0},
        "replicas": {"type": "integer", "required": True, "min": 0},
        "port": {"type": "integer", "required": True, "min": 0},
        "ingress": {
            "type": "boolean",
            "required": True,
        },
    }

    def __init__(self, stage_name: str, config: Dict[str, Any], root_dir: Path) -> None:
        """Constructor.

        :param stage_name: Name of parent stage config.
        :param config: Dictionary of configuration parameters.
        :param root_dir: The root directory of the project containing
            the bodywork config file and the stage directories.
        :raises BodyworkConfigValidationError: if any
            required configuration parameters are missing or invalid.
        """
        super().__init__(stage_name, config, root_dir)
        service_config = config["service"]
        data_validator = DictDataValidator(self.SCHEMA_SERVICE)
        self._missing_or_invalid_param += data_validator.find_errors_in(
            service_config, prefix=f"stages.{stage_name}.service."
        )
        if not self._missing_or_invalid_param:
            self.max_startup_time = service_config["max_startup_time_seconds"]
            self.replicas = service_config["replicas"]
            self.port = service_config["port"]
            self.create_ingress = service_config["ingress"]
        else:
            raise BodyworkConfigValidationError(self._missing_or_invalid_param)


def _parse_dag_definition(dag_definition: str) -> DAG:
    """Parse DAG definition string.

    :param dag_definition: A DAG definition in string format.
    :raises ValueError: If any 'null' (zero character) stage names are
        found.
    :return: A list of steps, where each step is a list of Bodywork
        project stage names (containing a list of stages to run in each
        step).
    """
    steps = dag_definition.replace(" ", "").split(">>")
    stages_in_steps = [step.split(",") for step in steps]
    steps_with_null_stages = [
        str(n)
        for n, step in enumerate(stages_in_steps, start=1)
        for stage in step
        if stage == ""
    ]
    if len(steps_with_null_stages) > 0:
        msg = (
            f'null stages found in step {", ".join(steps_with_null_stages)} when '
            f"parsing DAG definition"
        )
        raise ValueError(msg)
    return stages_in_steps


def _check_workflow_stages_are_configured(
    workflow: Iterable[Iterable[str]], stages: Iterable[str]
) -> Sequence[str]:
    """Identify stages in workflow that have not been configured.

    :param workflow: A project DAG parsed into a Bodywork workflow.
    :param stages: List of stages that have been configured.
    :return: List of missing stage messages.
    """
    stages_in_workflow = [stage for step in workflow for stage in step]
    missing_stages = [
        f"project.workflow -> cannot find valid stage @ stages.{stage}"
        for stage in stages_in_workflow
        if stage not in stages
    ]
    return missing_stages
