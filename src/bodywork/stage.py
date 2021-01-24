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
This module contains all of the functions and classes required to
download theproject code and run stages.
"""
from pathlib import Path
from subprocess import run, CalledProcessError

from .config import BodyworkConfig
from .constants import DEFAULT_PROJECT_DIR, STAGE_CONFIG_FILENAME, REQUIREMENTS_FILENAME
from .exceptions import BodyworkStageConfigError, BodyworkStageFailure
from .git import download_project_code_from_repo
from .logs import bodywork_log_factory


class Stage:
    """Class for generic stage data."""

    def __init__(self, name: str, config: BodyworkConfig, path_to_stage_dir: Path):
        """Constructor.

        :param name: Stage name, which must be the same as the stage
            directory name.
        :param config: Stage configuration data from parsed stage config
            file.
        :param path_to_stage_dir: The path to the specific stage
            directory.
        :raises BodyworkStageConfigError: If the name of the executable
            script within the stage directory has not been specified in
            the config.
        :raises FileExistsError: If the executable script or
            requirements.txt files cannot be found in the stage
            directory.
        """
        try:
            executable_script = config['default']['EXECUTABLE_SCRIPT']
        except KeyError as e:
            raise BodyworkStageConfigError('EXECUTABLE_SCRIPT', 'default', name) from e

        executable_script_path = path_to_stage_dir / executable_script
        if not executable_script_path.exists():
            msg = f'Cannot find {executable_script_path} in stage={name}'
            raise FileExistsError(msg)

        requirements_file_path = path_to_stage_dir / REQUIREMENTS_FILENAME
        if not requirements_file_path.exists():
            raise FileExistsError(f'Cannot find {requirements_file_path}')

        try:
            cpu_request = float(config['default']['CPU_REQUEST'])
        except (KeyError, TypeError) as e:
            raise BodyworkStageConfigError('CPU_REQUEST', 'default', name) from e

        try:
            memory_request = int(config['default']['MEMORY_REQUEST_MB'])
        except (KeyError, TypeError) as e:
            raise BodyworkStageConfigError('MEMORY_REQUEST_MB', 'default', name) from e

        try:
            env_vars_from_secrets = [
                (secret_name.lower(), secret_key.upper())
                for secret_key, secret_name in config['secrets'].items()
            ]
            self.env_vars_from_secrets = env_vars_from_secrets
        except KeyError:
            self.env_vars_from_secrets = []

        self.name = name
        self.path_to_stage_dir = path_to_stage_dir
        self.config = config
        self.executable_script_path = executable_script_path
        self.requirements_file_path = requirements_file_path
        self.cpu_request = cpu_request
        self.memory_request = memory_request

    def __eq__(self, other) -> bool:
        """Object equality operator.

        :param other: Other Stage object to compare this one too.
        """
        if self.path_to_stage_dir == other.path_to_stage_dir:
            return True
        else:
            return False


class BatchStage(Stage):
    """Class for batch stage data."""

    def __init__(self, name: str, config: BodyworkConfig, path_to_stage_dir: Path):
        """Constructor.

        :param name: Stage name, which must be the same as the stage
            directory name.
        :param config: Stage configuration data from parsed stage config
            file.
        :param path_to_stage_dir: The path to the specific stage
            directory.
        :raises BodyworkStageConfigError: If mandatory batch stage
            parameters have not been set: RETRIES, MAX_COMPLETION_TIME_SECONDS.
        """
        try:
            retries = int(config['batch']['RETRIES'])
        except (KeyError, ValueError) as e:
            raise BodyworkStageConfigError('RETRIES', 'batch', name) from e

        try:
            max_completion_time = int(config['batch']['MAX_COMPLETION_TIME_SECONDS'])
        except (KeyError, ValueError) as e:
            time_param_error = BodyworkStageConfigError(
                'MAX_COMPLETION_TIME_SECONDS',
                'batch',
                name
            )
            raise time_param_error from e

        self.retries = retries
        self.max_completion_time = max_completion_time
        super().__init__(name, config, path_to_stage_dir)


class ServiceStage(Stage):
    """Class for service stage data."""

    def __init__(self, name: str, config: BodyworkConfig, path_to_stage_dir: Path):
        """Constructor.

        :param name: Stage name, which must be the same as the stage
            directory name.
        :param config: Stage configuration data from parsed stage config
            file.
        :param path_to_stage_dir: The path to the specific stage
            directory.
        :raises BodyworkStageConfigError: If mandatory service stage
            parameters have not been set: REPLICAS,
            MAX_STARTUP_TIME_SECONDS and PORT.
        """
        try:
            replicas = int(config['service']['REPLICAS'])
        except (KeyError, ValueError) as e:
            raise BodyworkStageConfigError('REPLICAS', 'service', name) from e

        try:
            max_startup_time = int(config['service']['MAX_STARTUP_TIME_SECONDS'])
        except (KeyError, ValueError) as e:
            time_param_error = BodyworkStageConfigError(
                'MAX_STARTUP_TIME_SECONDS',
                'batch',
                name
            )
            raise time_param_error from e

        try:
            port = int(config['service']['PORT'])
        except (KeyError, ValueError) as e:
            raise BodyworkStageConfigError('PORT', 'service', name) from e

        self.replicas = replicas
        self.max_startup_time = max_startup_time
        self.port = port
        super().__init__(name, config, path_to_stage_dir)


def stage_factory(path_to_stage_dir: Path) -> Stage:
    """Create stage data object from stage directory contents.

    :param path_to_stage_dir: Path to the directory containing the files
        required for a Bodywork stage.
    :raises FileExistsError: if path_to_stage_dir does not exist.
    :raises BodyworkStageConfigError: If the STAGE_TYPE variable cannot
        be found or recognised (must be 'batch' or 'service').
    :return: A stage data object.
    """
    if not path_to_stage_dir.exists():
        msg = f'Bodywork stage directory {path_to_stage_dir} does not exist'
        raise FileExistsError(msg)
    stage_name = path_to_stage_dir.name
    path_to_config_file = path_to_stage_dir / STAGE_CONFIG_FILENAME
    stage_config = BodyworkConfig(path_to_config_file)
    try:
        stage_type = stage_config['default']['STAGE_TYPE']
        if stage_type == 'batch':
            return BatchStage(stage_name, stage_config, path_to_stage_dir)
        elif stage_type == 'service':
            return ServiceStage(stage_name, stage_config, path_to_stage_dir)
        else:
            msg = f'STAGE_TYPE={stage_type} is invalid - must be one of batch or service'
            raise RuntimeError(msg)
    except (KeyError, RuntimeError) as e:
        raise BodyworkStageConfigError('STAGE_TYPE', 'default', stage_name) from e


def run_stage(
    stage_name: str,
    repo_url: str,
    repo_branch: str = 'master',
    cloned_repo_dir: Path = DEFAULT_PROJECT_DIR
) -> None:
    """Retreive latest project code and run the chosen stage.

    :param stage_name: The Bodywork project stage name.
    :param repo_url: Git repository URL.
    :param repo_branch: The Git branch to download, defaults to 'master'.
    :param cloned_repo_dir: The name of the directory int which the
        repository will be cloned, defaults to DEFAULT_PROJECT_DIR.
    :raises RuntimeError: If the executable script exits with a non-zero
        exit code (i.e. fails).
    """
    log = bodywork_log_factory()
    log.info(f'attempting to run stage={stage_name} from {repo_branch} branch of repo'
             f' at {repo_url}')
    download_project_code_from_repo(repo_url, repo_branch, cloned_repo_dir)
    path_to_stage_dir = cloned_repo_dir / stage_name
    stage = stage_factory(path_to_stage_dir)
    try:
        _install_python_requirements(stage.requirements_file_path)
        run(['python', stage.executable_script_path], check=True)
        log.info(f'successfully ran stage={stage_name} from {repo_branch} branch of repo'
                 f' at {repo_url}')
    except CalledProcessError as e:
        stage_failure_exception = BodyworkStageFailure(stage_name, e.cmd, e.stderr)
        log.error(stage_failure_exception)
        raise stage_failure_exception from e


def _install_python_requirements(path_to_requirements_file: Path) -> None:
    """Install the Python dependencies for a Bodywork project stage.

    :param path_to_requirements_file: Path to requirements.txt flile for
         the stage.
    :raises RuntimeError: If there was an error when installing requirements.
    """
    try:
        run(['pip', 'install', '-r', path_to_requirements_file], check=True)
    except CalledProcessError as e:
        msg = f'Cannot install stage requirements: {e.cmd} failed with {e.stderr}'
        raise RuntimeError(msg)
