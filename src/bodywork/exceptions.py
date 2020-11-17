"""
This module contains custom Bodywork exceptions to be used throughout
all modules and tests. All Bodywork specific exceptions should be kept
in this module to make them easier to locate when importing the package
externally.
"""
from typing import Iterable

from kubernetes.client import V1Job

from .constants import PROJECT_CONFIG_FILENAME


class BodyworkJobFailure(Exception):
    def __init__(self, failed_jobs: Iterable[V1Job]):
        failed_jobs_msg = [
            f'job={job.metadata.name} in namespace={job.metadata.namespace}'
            for job in failed_jobs
        ]
        msg = f'{"; ".join(failed_jobs_msg)} have failed'
        super().__init__(msg)


class BodyworkProjectConfigError(Exception):
    def __init__(self, missing_param_name: str):
        msg = (f'cannot find parameter={missing_param_name} in '
               f'{PROJECT_CONFIG_FILENAME} file')
        super().__init__(msg)


class BodyworkWorkflowExecutionError(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class BodyworkStageConfigError(Exception):
    def __init__(self, stage_name: str, config_key: str, config_section: str):
        msg = (f'{config_key} in [{config_section}] section of {stage_name} stage '
               f'config file is missing or mis-specified')
        super().__init__(msg)


class BodyworkStageFailure(Exception):
    def __init__(self, stage_name: str, cmd: str, stderr: str):
        msg = f'Stage {stage_name} failed - calling {cmd} returned {stderr}'
        super().__init__(msg)
