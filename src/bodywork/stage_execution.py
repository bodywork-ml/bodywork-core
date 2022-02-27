# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020-2022  Bodywork Machine Learning Ltd.

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
download the project code and run stages.
"""
from enum import Enum
from os import environ
from pathlib import Path
from subprocess import run, CalledProcessError
from typing import Sequence

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

from .config import BodyworkConfig
from .constants import DEFAULT_PROJECT_DIR, PROJECT_CONFIG_FILENAME
from .exceptions import BodyworkStageFailure
from .git import download_project_code_from_repo
from .logs import bodywork_log_factory


class ExecutableType(Enum):
    "Executable file type."

    JUPYTER_NB = ".ipynb"
    PY_MODULE = ".py"


def run_stage(
    stage_name: str,
    repo_url: str,
    repo_branch: str = None,
    cloned_repo_dir: Path = DEFAULT_PROJECT_DIR,
) -> None:
    """Retrieve latest project code and run the chosen stage.

    :param stage_name: The Bodywork project stage name.
    :param repo_url: Git repository URL.
    :param repo_branch: The Git branch to download, defaults to None.
    :param cloned_repo_dir: The name of the directory int which the
        repository will be cloned, defaults to DEFAULT_PROJECT_DIR.
    :raises RuntimeError: If the executable script exits with a non-zero
        exit code (i.e. fails).
    """
    log = bodywork_log_factory()
    log.info(
        f"Attempting to run stage = {stage_name} from {repo_branch} branch of repo "
        f"at {repo_url}"
    )
    try:
        download_project_code_from_repo(repo_url, repo_branch, cloned_repo_dir)
        config_file_path = cloned_repo_dir / PROJECT_CONFIG_FILENAME
        project_config = BodyworkConfig(config_file_path)
        stage = project_config.stages[stage_name]
        environ["PYTHONPATH"] = str(cloned_repo_dir.absolute())
        if stage.requirements:
            _install_python_requirements(stage.requirements)
        executable_type = _infer_executable_type(stage.executable_module)
        if executable_type is ExecutableType.JUPYTER_NB:
            notebook = nbformat.read(
                stage.executable_module_path, as_version=nbformat.NO_CONVERT
            )
            nb_runner = ExecutePreprocessor()
            nb_runner.preprocess(
                notebook,
                {"metadata": {"path": stage.executable_module_path.parent}},
            )
        else:
            run(
                ["python", stage.executable_module, *stage.args],
                check=True,
                cwd=stage.executable_module_path.parent,
                encoding="utf-8",
            )
        log.info(
            f"Successfully ran stage = {stage_name} from {repo_branch} branch of repo "
            f"at {repo_url}"
        )
    except Exception as e:
        stage_failure_exception = BodyworkStageFailure(stage_name, e.__repr__())
        log.error(stage_failure_exception)
        raise stage_failure_exception from e


def _install_python_requirements(requirements: Sequence[str]) -> None:
    """Install the Python dependencies for a Bodywork project stage.

    :param requirements: List of requirements to be installed.
    :raises RuntimeError: If there was an error when installing requirements.
    """
    try:
        run(
            ["pip", "install", *requirements],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
    except CalledProcessError as e:
        msg = f"Cannot install stage requirements: {e.cmd} failed with {e.stderr}"
        raise RuntimeError(msg)


def _infer_executable_type(file_name: str) -> ExecutableType:
    """Infer the type of Python executable from the filename.

    :param file_name: The name of the executable.
    :raises ValueError: If the filename is not a valid Jupyter notebook
        or Python module filename.
    """
    if file_name.endswith(".ipynb"):
        return ExecutableType.JUPYTER_NB
    elif file_name.endswith(".py"):
        return ExecutableType.PY_MODULE
    else:
        raise ValueError(f"Bodywork cannot execute {file_name}")
