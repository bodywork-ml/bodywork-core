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
High-level interface to the Kubernetes cronjobs API as used to create
and manage cronjobs that execute Bodywork project workflows.
"""
from datetime import datetime
from typing import Dict, Union

from kubernetes import client as k8s

from ..constants import (
    BODYWORK_DOCKER_IMAGE,
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
    SSH_GITHUB_KEY_ENV_VAR,
    SSH_GITHUB_SECRET_NAME
)


def configure_cronjob(
    cron_schedule: str,
    namespace: str,
    project_name: str,
    project_repo_url: str,
    project_repo_branch: str = 'master',
    retries: int = 2,
    successful_jobs_history_limit: int = 1,
    failed_jobs_history_limit: int = 1,
    image: str = BODYWORK_DOCKER_IMAGE,
) -> k8s.V1beta1CronJob:
    """Configure a Bodywork batch stage k8s cron-job.

    A cron-job is a k8s job that is executed on a cron-like schedule. In
    this particular instance, the job will execute the `run_workflow`
    function that will orchestrate the required jobs and deployments.

    :param cron_schedule: A valid cron schedule definition.
    :param namespace: The namespace to deploy the cronjob to.
    :param project_name: The name of the Bodywork project that the stage
        belongs to.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The Bodywork project Git repository
        branch to use, defaults to 'master'.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param successful_jobs_history_limit: The number of successful job
        runs (pods) to keep, defaults to 1.
    :param failed_jobs_history_limit: The number of unsuccessful job
        runs (pods) to keep, defaults to 1.
    :param image: Docker image to use for running the stage within,
        defaults to BODYWORK_DOCKER_IMAGE.
    :return: A configured k8s cronjob object.
    """
    vcs_env_vars = [
        k8s.V1EnvVar(
            name=SSH_GITHUB_KEY_ENV_VAR,
            value_from=k8s.V1EnvVarSource(
                secret_key_ref=k8s.V1SecretKeySelector(
                    key=SSH_GITHUB_KEY_ENV_VAR,
                    name=SSH_GITHUB_SECRET_NAME,
                    optional=True
                )
            )
        )
    ]
    container = k8s.V1Container(
        name='bodywork',
        image=image,
        image_pull_policy='Always',
        env=vcs_env_vars,
        command=['bodywork', 'workflow'],
        args=[f'--namespace={namespace}', project_repo_url, project_repo_branch]
    )
    pod_spec = k8s.V1PodSpec(
        service_account_name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
        containers=[container],
        restart_policy='Never'
    )
    pod_template_spec = k8s.V1PodTemplateSpec(
        spec=pod_spec
    )
    job_spec = k8s.V1JobSpec(
        template=pod_template_spec,
        completions=1,
        backoff_limit=retries
    )
    job_template = k8s.V1beta1JobTemplateSpec(
        spec=job_spec
    )
    cronjob_spec = k8s.V1beta1CronJobSpec(
        schedule=cron_schedule,
        successful_jobs_history_limit=successful_jobs_history_limit,
        failed_jobs_history_limit=failed_jobs_history_limit,
        job_template=job_template
    )
    cronjob = k8s.V1beta1CronJob(
        metadata=k8s.V1ObjectMeta(
            name=project_name,
            namespace=namespace
        ),
        spec=cronjob_spec
    )
    return cronjob


def create_cronjob(cron_job: k8s.V1Job) -> None:
    """Create a cron-job on a k8s cluster.

    :param cron_job: A configured cron-job object.
    """
    k8s.BatchV1beta1Api().create_namespaced_cron_job(
        body=cron_job,
        namespace=cron_job.metadata.namespace
    )


def delete_cronjob(namespace: str, name: str) -> None:
    """Delete a cron-job on a k8s cluster.

    :param namespace: Namespace in which to look for the secret to
        delete.
    :param name: The name of the secret to be deleted.
    """
    k8s.BatchV1beta1Api().delete_namespaced_cron_job(
        name=name,
        namespace=namespace,
        body=k8s.V1DeleteOptions(propagation_policy='Background')
    )


def list_cronjobs(namespace: str) -> Dict[str, Dict[str, str]]:
    """Get all cronjobs and their high-level info.

    :param namespace: Namespace in which to list cronjobs.
    """
    cronjobs = k8s.BatchV1beta1Api().list_namespaced_cron_job(
        namespace=namespace
    )
    cronjob_info = {
        cronjob.metadata.name: {
            'schedule': cronjob.spec.schedule,
            'last_scheduled_time': cronjob.status.last_schedule_time,
            'git_url': (
                cronjob.spec
                .job_template
                .spec
                .template
                .spec
                .containers[0]
                .args[1]
            ),
            'git_branch': (
                cronjob
                .spec
                .job_template
                .spec
                .template
                .spec
                .containers
                [0]
                .args[2]
            )
        }
        for cronjob in cronjobs.items
    }
    return cronjob_info


def list_workflow_jobs(
    namespace: str,
    cronjob_name: str
) -> Dict[str, Dict[str, Union[datetime, bool]]]:
    """Get workflow-runner jobs that were triggered by a cronjob.

    Returns status information for all workflow jobs owned by a cronjob.

    :param namespace: Namespace in which to list workflow jobs.
    :param cronjob_name: Name of cronjob that triggered workflow job.
    :return: Dictionary of workflow jobs each mapping to a dictionary of
        status information fields for the workflow.
    """
    workflow_jobs_query = k8s.BatchV1Api().list_namespaced_job(
        namespace=namespace
    )
    workflow_jobs_info = {
        workflow_job.metadata.name: {
            'start_time': workflow_job.status.start_time,
            'completion_time': workflow_job.status.completion_time,
            'active': True if workflow_job.status.active else False,
            'succeeded': True if workflow_job.status.succeeded else False,
            'failed': True if workflow_job.status.failed else False
        }
        for workflow_job in workflow_jobs_query.items
        if workflow_job.metadata.name.startswith(cronjob_name)
    }
    return workflow_jobs_info
