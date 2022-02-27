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
This module contains functions for managing Kubernetes workflow jobs.
They are targeted for use via the CLI.
"""
import re
from pathlib import Path

from .terminal import print_dict, print_info, print_pod_logs, print_warn
from .. import k8s
from ..constants import BODYWORK_DOCKER_IMAGE, SSH_SECRET_NAME


def create_workflow_job(
    namespace: str,
    job_name: str,
    project_repo_url: str,
    project_repo_branch: str = None,
    retries: int = 2,
    image: str = BODYWORK_DOCKER_IMAGE,
    ssh_key_path: str = None,
    secrets_group: str = None,
) -> None:
    """Create a new workflow job within a namespace.

    :param namespace: The namespace to deploy the job to.
    :param job_name: The name of the Bodywork job.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The branch of the Bodywork project Git
        repository that will be used as the executable codebase,
        defaults to None.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param image: Docker image to use for running the stages within,
        defaults to BODYWORK_DOCKER_IMAGE.
    :param ssh_key_path: SSH key filepath.
    :param secrets_group: Secrets group to use if using SSH.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if _is_existing_workflow_job(namespace, job_name):
        print_warn(f"Cannot create workflow-job={job_name} as it already exists.")
        return None
    if ssh_key_path:
        if not secrets_group:
            print_warn("Please specify Secrets Group in config to use SSH.")
            return None
        try:
            k8s.create_ssh_key_secret_from_file(secrets_group, Path(ssh_key_path))
        except FileNotFoundError:
            print_warn(f"Could not find SSH key file at: {ssh_key_path}")
            return None
    if secrets_group:
        if not k8s.secret_exists(
            namespace, k8s.create_complete_secret_name(SSH_SECRET_NAME, secrets_group)
        ):
            print_warn(
                f"Could not find SSH secret: {SSH_SECRET_NAME} in group: {secrets_group}"
            )
        env_vars = [k8s.create_secret_env_variable(secrets_group)]
    else:
        env_vars = None

    configured_job = k8s.configure_workflow_job(
        namespace,
        project_repo_url,
        project_repo_branch,
        retries,
        image,
        job_name,
        container_env_vars=env_vars,
    )
    k8s.create_workflow_job(configured_job)
    print_info(f"Created workflow-job={job_name}.")


def delete_workflow_job(namespace: str, job_name: str) -> None:
    """Delete workflow job from a specific namespace.

    :param namespace: Namespace where the job resides.
    :param job_name: Name of the job to delete.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if not _is_existing_workflow_job(namespace, job_name):
        print_warn(f"Could not find workflow-job={job_name}.")
        return None
    k8s.delete_job(namespace, job_name)
    print_info(f"Deleted workflow-job={job_name}.")


def create_workflow_cronjob(
    namespace: str,
    schedule: str,
    job_name: str,
    project_repo_url: str,
    project_repo_branch: str = None,
    retries: int = 2,
    workflow_job_history_limit: int = 1,
    ssh_key_path: str = None,
    secrets_group: str = None,
) -> None:
    """Create a new cronjob within a namespace.

    :param namespace: The namespace to deploy the job to.
    :param schedule: A valid cron schedule definition.
    :param job_name: The name of the Bodywork the job to create.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The branch of the Bodywork project Git
        repository that will be used as the executable codebase,
        defaults to None.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param workflow_job_history_limit: Minimum number of
        historical workflow jobs, so logs can be retrieved.
    :param ssh_key_path: SSH key filepath.
    :param secrets_group: Secrets group to use if using SSH.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if _is_existing_workflow_cronjob(namespace, job_name):
        print_warn(f"Cannot create cronjob={job_name} as it already exists.")
        return None
    if not _is_valid_cron_schedule(schedule):
        print_warn(f"Invalid cronjob schedule: {schedule}.")
        return None
    if ssh_key_path:
        if not secrets_group:
            print_warn("Please specify Secrets Group in config to use SSH.")
            return None
        try:
            k8s.create_ssh_key_secret_from_file(secrets_group, Path(ssh_key_path))
        except FileNotFoundError:
            print_warn(f"Could not find SSH key file at: {ssh_key_path}")
            return None
    if secrets_group:
        if not k8s.secret_exists(
            namespace, k8s.create_complete_secret_name(SSH_SECRET_NAME, secrets_group)
        ):
            print_warn(
                f"Could not find SSH secret: {SSH_SECRET_NAME} in group: {secrets_group}"
            )
        env_vars = [k8s.create_secret_env_variable(secrets_group)]
    else:
        env_vars = None
    configured_job = k8s.configure_workflow_cronjob(
        schedule,
        namespace,
        job_name,
        project_repo_url,
        project_repo_branch,
        retries,
        workflow_job_history_limit,
        workflow_job_history_limit,
        env_vars=env_vars,
    )
    k8s.create_workflow_cronjob(configured_job)
    print_info(f"Created cronjob={job_name}.")


def update_workflow_cronjob(
    namespace: str,
    job_name: str,
    schedule: str = None,
    project_repo_url: str = None,
    project_repo_branch: str = None,
    retries: int = None,
    workflow_job_history_limit: int = None,
) -> None:
    """Update a new cronjob within a namespace.

    :param namespace: The namespace the job resides in.
    :param job_name: The name of the cronjob.
    :param schedule: A valid cron schedule definition.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The branch of the Bodywork project Git
        repository that will be used as the executable codebase,
        defaults to None.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param workflow_job_history_limit: Minimum number of
        historical workflow jobs, so logs can be retrieved.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if not _is_existing_workflow_cronjob(namespace, job_name):
        print_warn(f"Could not find cronjob={job_name}.")
        return None
    if schedule and not _is_valid_cron_schedule(schedule):
        print_warn(f"Invalid cronjob schedule: {schedule}.")
        return None
    k8s.update_workflow_cronjob(
        namespace,
        job_name,
        schedule,
        project_repo_url,
        project_repo_branch,
        retries,
        workflow_job_history_limit,
        workflow_job_history_limit,
    )
    print_info(f"Updated cronjob={job_name}.")


def delete_workflow_cronjob(namespace: str, job_name: str) -> None:
    """Create a new cronjob within a k8s namespace.

    :param namespace: The namespace where the cronjob resides.
    :param job_name: The name of the cronjob to be deleted.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if not _is_existing_workflow_cronjob(namespace, job_name):
        print_warn(f"Could not find cronjob={job_name}.")
        return None
    k8s.delete_workflow_cronjob(namespace, job_name)
    print_info(f"Deleted cronjob={job_name}.")


def display_cronjobs(namespace: str, job_name: str = None) -> None:
    """Print cronjobs to stdout.

    :param namespace: Namespace in which to look for cronjobs.
    :param job_name: Name of cronjob resource, defaults to None.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    cronjobs_info = k8s.list_workflow_cronjobs(namespace)
    if job_name:
        print_dict(cronjobs_info[job_name], job_name)
    else:
        table_data = {name: data["git_url"] for name, data in cronjobs_info.items()}
        print_dict(table_data, "cronjobs", "Name", "Git Repository URL")


def display_workflow_job_history(namespace: str, job_name: str) -> None:
    """Print info on workflow jobs, triggered by a cronjob, to stdout.

    :param namespace: Namespace in which to look for cronjobs.
    :param job_name: Name of the cronjob.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    workflow_jobs_info = k8s.list_workflow_jobs(namespace, job_name)
    for name, data in workflow_jobs_info.items():
        print_dict(data, f"workflow job = {name}")


def display_workflow_job_logs(namespace: str, job_name: str) -> None:
    """Print workflow job logs to stdout.

    :param namespace: Namespace in which the workflow job exists.
    :param job_name: The full name of the specific workflow job
        executed - e.g. NAME_OF_PROJECT-12345.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    workflow_job_pod_name = k8s.get_latest_pod_name(namespace, job_name)
    if workflow_job_pod_name is None:
        print_warn(f"Cannot find pod for workflow job={job_name}.")
        return None
    workflow_job_logs = k8s.get_pod_logs(namespace, workflow_job_pod_name)
    print_pod_logs(workflow_job_logs, f"logs for workflow execution = {job_name}")


def _is_existing_workflow_job(namespace: str, job_name: str) -> bool:
    """Can the named job be found in the namespace.

    :param namespace: The namespace to look in.
    :param job_name: The name of the Bodywork the job.
    :return: A boolean flag.
    """
    jobs_in_namespace = k8s.list_workflow_jobs(namespace, job_name)
    return True if job_name in jobs_in_namespace.keys() else False


def _is_existing_workflow_cronjob(namespace: str, job_name: str) -> bool:
    """Can the named cronjob be found in the namespace.

    :param namespace: The namespace to look in.
    :param job_name: The name of the Bodywork the job.
    :return: A boolean flag.
    """
    cronjobs_in_namespace = k8s.list_workflow_cronjobs(namespace)
    return True if job_name in cronjobs_in_namespace.keys() else False


def _is_valid_cron_schedule(schedule: str) -> bool:
    """Does a string represent a valid cron schedule.

    :param schedule: A string describing a cron schedule.
    :return: A boolean flag.
    """
    parsed_schedule = [e for e in schedule.split(" ")]
    if len(parsed_schedule) != 5:
        return False

    minutes_pattern_matches = re.fullmatch(
        r"^([1-5]?[0-9](,|$))+" r"|^(\*|[1-5]?[0-9]-[1-5]?[0-9])(\/[1-5]?[0-9]$|$)",
        parsed_schedule[0],
    )
    if minutes_pattern_matches is None:
        return False

    hours_pattern_matches = re.fullmatch(
        r"^((2[0-3]|1?[0-9])(,|$))+"
        r"|^(\*|(2[0-3]|1?[0-9])-(2[0-3]|1?[0-9]))(\/(2[0-3]|1?[0-9])$|$)",
        parsed_schedule[1],
    )
    if hours_pattern_matches is None:
        return False

    day_of_the_month_pattern_matches = re.fullmatch(
        r"^((3[0-1]|[1-2]?[0-9])(,|$))+"
        r"|^(\*|(3[0-1]|[1-2]?[0-9])-(3[0-1]|[1-2]?[0-9]))(\/(3[0-1]|[1-2]?[0-9])$|$)",  # noqa
        parsed_schedule[2],
    )
    if day_of_the_month_pattern_matches is None:
        return False

    month_pattern_matches = re.fullmatch(
        r"^((1[0-2]|[0-9])(,|$))+"
        r"|^(\*|(1[0-2]|[0-9])-(1[0-2]|[0-9]))(\/(1[0-2]|[0-9])$|$)",
        parsed_schedule[3],
    )
    if month_pattern_matches is None:
        return False

    day_of_week_pattern_matches = re.fullmatch(
        r"^([0-6](,|$))+" r"|^(\*|[0-6]-[0-6])(\/[0-6]$|$)", parsed_schedule[4]
    )
    if day_of_week_pattern_matches is None:
        return False

    return True
