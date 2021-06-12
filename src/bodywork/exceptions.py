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
This module contains custom Bodywork exceptions to be used throughout
all modules and tests. All Bodywork specific exceptions should be kept
in this module to make them easier to locate when importing the package
externally.
"""
from pathlib import Path
from typing import Iterable, Sequence

from kubernetes.client import V1Job

from .constants import BODYWORK_VERSION, BODYWORK_CONFIG_VERSION


class BodyworkJobFailure(Exception):
    def __init__(self, failed_jobs: Iterable[V1Job]):
        failed_jobs_msg = [
            f"job={job.metadata.name} in namespace={job.metadata.namespace}"
            for job in failed_jobs
        ]
        msg = f'{"; ".join(failed_jobs_msg)} have failed'
        super().__init__(msg)


class BodyworkConfigError(Exception):
    pass


class BodyworkConfigParsingError(BodyworkConfigError):
    def __init__(self, config_file_path: Path):
        msg = f"cannot parse YAML from {config_file_path}"
        super().__init__(msg)


class BodyworkConfigMissingSectionError(BodyworkConfigError):
    def __init__(self, missing_sections: Sequence[str]):
        msg = f'Bodywork config file missing sections: {", ".join(missing_sections)}'
        super().__init__(msg)


class BodyworkConfigValidationError(BodyworkConfigError):
    def __init__(self, missing_params: Sequence[str]):
        self.missing_params = missing_params
        msg = (
            f"Bodywork config missing or invalid parameters: "
            f'{", ".join(missing_params)}'
        )
        super().__init__(msg)


class BodyworkConfigVersionMismatchError(BodyworkConfigError):
    def __init__(self, version: str):
        msg = (
            f"Bodywork config file has schema version {version}, when Bodywork "
            f"version {BODYWORK_VERSION} requires schema version "
            f"{BODYWORK_CONFIG_VERSION}"
        )
        super().__init__(msg)


class BodyworkWorkflowExecutionError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class BodyworkStageFailure(Exception):
    def __init__(self, stage_name: str, info: str):
        msg = f'Stage {stage_name} failed - {info}'
        super().__init__(msg)


class BodyworkNamespaceError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class BodyworkDockerImageError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class BodyworkGitError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
