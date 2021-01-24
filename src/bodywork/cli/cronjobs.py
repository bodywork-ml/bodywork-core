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
This module contains functions for managing Kubernetes cronjobs. They
are targeted for use via the CLI.
"""
import re

from .. import k8s


def create_cronjob_in_namespace(
    namespace: str,
    schedule: str,
    project_name: str,
    project_repo_url: str,
    project_repo_branch: str = 'master',
    retries: int = 2,
) -> None:
    """Create a new cronjob within a k8s namespace.

    :param namespace: The namespace to deploy the cronjob to.
    :param schedule: A valid cron schedule definition.
    :param project_name: The name of the Bodywork project attached to
        the cronjob.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The branch of the Bodywork project Git
        repository that will be used as the executable codebase,
        defaults to 'master'.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    """
    if not k8s.namespace_exists(namespace):
        print(f'namespace={namespace} could not be found on k8s cluster')
        return None
    if _is_existing_cronjob(namespace, project_name):
        print(f'cronjob={project_name} already exists in namespace={namespace}')
        return None
    if not _is_valid_cron_schedule(schedule):
        print(f'schedule={schedule} is not a valid cron schedule')
        return None
    configured_job = k8s.configure_cronjob(
        schedule,
        namespace,
        project_name,
        project_repo_url,
        project_repo_branch,
        retries
    )
    k8s.create_cronjob(configured_job)
    print(f'cronjob={project_name} created in namespace={namespace}')


def delete_cronjob_in_namespace(namespace: str, project_name: str) -> None:
    """Create a new cronjob within a k8s namespace.

    :param namespace: The namespace to deploy the cronjob to.
    :param project_name: The name of the Bodywork project attached to
        the cronjob to be deleted.
    """
    if not k8s.namespace_exists(namespace):
        print(f'namespace={namespace} could not be found on k8s cluster')
        return None
    if not _is_existing_cronjob(namespace, project_name):
        print(f'cronjob={project_name} not found in namespace={namespace}')
        return None
    k8s.delete_cronjob(namespace, project_name)
    print(f'cronjob={project_name} deleted from namespace={namespace}')


def display_cronjobs_in_namespace(namespace: str) -> None:
    """Print cronjobs to stdout.

    :param namespace: Namespace in which to look for cronjobs.
    """
    if not k8s.namespace_exists(namespace):
        print(f'namespace={namespace} could not be found on k8s cluster')
        return None
    cronjobs_info = k8s.list_cronjobs(namespace)
    print(f'cronjobs in namespace={namespace}:\n')
    print(
        f'{"NAME":<40}'
        f'{"SCHEDULE":<30}'
        f'{"LAST_ACTIVE":<25}'
        f'{"GIT_URL":<50}'
        f'{"GIT_BRANCH":<20}'
    )
    for name, data in cronjobs_info.items():
        print(
            f'{name:<40}'
            f'{data["schedule"]:<30}'
            f'{str(data["last_scheduled_time"]):<25}'
            f'{data["git_url"]:<50}'
            f'{data["git_branch"]:<20}'
        )


def display_cronjob_workflow_history(namespace: str, project_name: str) -> None:
    """Print info on workflow jobs, triggered by a cronjob, to stdout.

    :param namespace: Namespace in which to look for cronjobs.
    :param project_name: Name given to cronjob.
    """
    if not k8s.namespace_exists(namespace):
        print(f'namespace={namespace} could not be found on k8s cluster')
        return None
    workflow_jobs_info = k8s.list_workflow_jobs(namespace, project_name)
    print(
        f'recent workflow executions for cronjob={project_name} in '
        f'namespace={namespace}:\n'
    )
    print(
        f'{"JOB_NAME":<40}'
        f'{"START_TIME":<30}'
        f'{"COMPLETION_TIME":<30}'
        f'{"ACTIVE":<20}'
        f'{"SUCCEEDED":<20}'
        f'{"FAILED":<20}'
    )
    for name, data in workflow_jobs_info.items():
        print(
            f'{name:<40}'
            f'{str(data["start_time"]):<30}'
            f'{str(data["completion_time"]):<30}'
            f'{data["active"]:<20}'
            f'{data["succeeded"]:<20}'
            f'{data["failed"]:<20}'
        )


def display_cronjob_workflow_logs(namespace: str, workflow_job_name: str) -> None:
    """Print workflow job logs to stdout.

    :param namespace: Namespace in which the workflow job exists.
    :param workflow_job_name: The full name of the specific workflow job
        executed - e.g. NAME_OF_PROJECT-12345.
    """
    if not k8s.namespace_exists(namespace):
        print(f'namespace={namespace} could not be found on k8s cluster')
        return None
    workflow_job_pod_name = k8s.get_latest_pod_name(namespace, workflow_job_name)
    if workflow_job_pod_name is None:
        print(f'cannot find pod for workflow-job={workflow_job_name}')
        return None
    workflow_job_logs = k8s.get_pod_logs(namespace, workflow_job_pod_name)
    print(workflow_job_logs)


def _is_existing_cronjob(namespace: str, project_name: str) -> bool:
    """Can the named cronjob be found in the namespace.

    :param namespace: The namespace to look in.
    :param project_name: The name of the Bodywork project attached to
        the cronjob.
    :return: A boolean flag.
    """
    cronjobs_in_namespace = k8s.list_cronjobs(namespace)
    return True if project_name in cronjobs_in_namespace.keys() else False


def _is_valid_cron_schedule(schedule: str) -> bool:
    """Does a string represent a valid cron schedule.

    :param schedule: A string describing a cron schedule.
    :return: A boolean flag.
    """
    parsed_schedule = [e for e in schedule.split(' ')]
    if len(parsed_schedule) != 5:
        return False

    minutes_pattern_matches = re.fullmatch(
        r'^([1-5]?[0-9](,|$))+'
        r'|^(\*|[1-5]?[0-9]-[1-5]?[0-9])(\/[1-5]?[0-9]$|$)',
        parsed_schedule[0]
    )
    if minutes_pattern_matches is None:
        return False

    hours_pattern_matches = re.fullmatch(
        r'^((2[0-3]|1?[0-9])(,|$))+'
        r'|^(\*|(2[0-3]|1?[0-9])-(2[0-3]|1?[0-9]))(\/(2[0-3]|1?[0-9])$|$)',
        parsed_schedule[1]
    )
    if hours_pattern_matches is None:
        return False

    day_of_the_month_pattern_matches = re.fullmatch(
        r'^((3[0-1]|[1-2]?[0-9])(,|$))+'
        r'|^(\*|(3[0-1]|[1-2]?[0-9])-(3[0-1]|[1-2]?[0-9]))(\/(3[0-1]|[1-2]?[0-9])$|$)',  # noqa
        parsed_schedule[2]
    )
    if day_of_the_month_pattern_matches is None:
        return False

    month_pattern_matches = re.fullmatch(
        r'^((1[0-2]|[0-9])(,|$))+'
        r'|^(\*|(1[0-2]|[0-9])-(1[0-2]|[0-9]))(\/(1[0-2]|[0-9])$|$)',
        parsed_schedule[3]
    )
    if month_pattern_matches is None:
        return False

    day_of_week_pattern_matches = re.fullmatch(
        r'^([0-6](,|$))+'
        r'|^(\*|[0-6]-[0-6])(\/[0-6]$|$)',
        parsed_schedule[4]
    )
    if day_of_week_pattern_matches is None:
        return False

    return True
