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
High-level interface to the Kubernetes jobs and cronjobs APIs, as used
to create and manage cronjobs that execute Bodywork project workflows.
"""
import os
import random
from datetime import datetime
from typing import Dict, Union, List
from kubernetes import client as k8s

from ..constants import (
    BODYWORK_DOCKER_IMAGE,
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
    BODYWORK_WORKFLOW_JOB_TIME_TO_LIVE,
)
from .utils import make_valid_k8s_name


def configure_workflow_job(
    namespace: str,
    project_repo_url: str,
    project_repo_branch: str,
    retries: int = 2,
    image: str = BODYWORK_DOCKER_IMAGE,
    job_name: str = None,
    container_env_vars: List[k8s.V1EnvVar] = None,
) -> k8s.V1Job:
    """Configure a Bodywork workflow execution job.

    :param namespace: The namespace to deploy the job to.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The Bodywork project Git repository
        branch to use, defaults to None.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param image: Docker image to use for running the stage within,
        defaults to BODYWORK_DOCKER_IMAGE.
    :param job_name: Set the job name.
    :param container_env_vars: List of k8s environment variables to add.
    :return: A configured k8s job object.
    """
    container_args = (
        [project_repo_url, f"--branch={project_repo_branch}"]
        if project_repo_branch
        else [project_repo_url]
    )
    container = k8s.V1Container(
        name="bodywork",
        image=image,
        image_pull_policy="Always",
        env=container_env_vars,
        command=[
            "bodywork",
            "create",
            "deployment",
        ],
        args=container_args,
    )
    pod_spec = k8s.V1PodSpec(
        service_account_name=BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
        containers=[container],
        restart_policy="Never",
    )
    pod_template_spec = k8s.V1PodTemplateSpec(spec=pod_spec)
    job_spec = k8s.V1JobSpec(
        template=pod_template_spec,
        completions=1,
        backoff_limit=retries,
        ttl_seconds_after_finished=BODYWORK_WORKFLOW_JOB_TIME_TO_LIVE,
    )
    if not job_name:
        job_name = _create_job_name(project_repo_url, project_repo_branch)
    job = k8s.V1Job(
        metadata=k8s.V1ObjectMeta(
            name=make_valid_k8s_name(job_name),
            namespace=namespace,
            labels={"app": "bodywork", "deployment-name": job_name},
        ),
        spec=job_spec,
    )
    return job


def _create_job_name(project_repo_url: str, project_repo_branch: str) -> str:
    """Create unique job name.

    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The Bodywork project Git repository
        branch being used.
    """
    repo_name = os.path.splitext(os.path.basename(project_repo_url))[0]
    return f"{repo_name}-{project_repo_branch}-{random.randint(0,999999)}"


def create_workflow_job(job: k8s.V1Job) -> None:
    """Create a workflow execution job.

    :param job: A configured job object.
    """
    k8s.BatchV1Api().create_namespaced_job(body=job, namespace=job.metadata.namespace)


def configure_workflow_cronjob(
    cron_schedule: str,
    namespace: str,
    job_name: str,
    project_repo_url: str,
    project_repo_branch: str = None,
    retries: int = 2,
    successful_jobs_history_limit: int = 1,
    failed_jobs_history_limit: int = 1,
    image: str = BODYWORK_DOCKER_IMAGE,
    env_vars: List[k8s.V1EnvVar] = None,
) -> k8s.V1beta1CronJob:
    """Configure a Bodywork workflow cronjob.

    A cronjob is a k8s job that is executed on a cron-like schedule. In
    this particular instance, the job will execute the `run_workflow`
    function that will orchestrate the required jobs and deployments.

    :param cron_schedule: A valid cron schedule definition.
    :param job_name: The name to give the cronjob.
    :param namespace: Namespace to create cronjob in.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The Bodywork project Git repository
        branch to use, defaults to None.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param successful_jobs_history_limit: The number of successful job
        runs (pods) to keep, defaults to 1.
    :param failed_jobs_history_limit: The number of unsuccessful job
        runs (pods) to keep, defaults to 1.
    :param image: Docker image to use for running the stage within,
        defaults to BODYWORK_DOCKER_IMAGE.
    :param env_vars: List of k8s environment variables to add.
    :return: A configured k8s cronjob object.
    """
    job = configure_workflow_job(
        namespace=namespace,
        project_repo_url=project_repo_url,
        project_repo_branch=project_repo_branch,
        retries=retries,
        image=image,
        job_name=job_name,
        container_env_vars=env_vars,
    )
    job_template = k8s.V1beta1JobTemplateSpec(metadata=job.metadata, spec=job.spec)
    cronjob_spec = k8s.V1beta1CronJobSpec(
        schedule=cron_schedule,
        successful_jobs_history_limit=successful_jobs_history_limit,
        failed_jobs_history_limit=failed_jobs_history_limit,
        job_template=job_template,
    )
    cronjob = k8s.V1beta1CronJob(metadata=job.metadata, spec=cronjob_spec)
    return cronjob


def create_workflow_cronjob(cron_job: k8s.V1Job) -> None:
    """Create a cron-job on a k8s cluster.

    :param cron_job: A configured cron-job object.
    """
    k8s.BatchV1beta1Api().create_namespaced_cron_job(
        body=cron_job, namespace=cron_job.metadata.namespace
    )


def update_workflow_cronjob(
    namespace: str,
    name: str,
    schedule: str = None,
    project_repo_url: str = None,
    project_repo_branch: str = None,
    retries: int = None,
    successful_jobs_history_limit: int = None,
    failed_jobs_history_limit: int = None,
) -> None:
    """Update a Bodywork workflow cronjob.

    :param name: The name  of the cronjob.
    :param namespace: Namespace the cronjob resides in.
    :param schedule: A valid cron schedule definition.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The Bodywork project Git repository
        branch to use, defaults to None.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param successful_jobs_history_limit: The number of successful job
        runs (pods) to keep, defaults to 1.
    :param failed_jobs_history_limit: The number of unsuccessful job
        runs (pods) to keep, defaults to 1.
    """

    if not schedule:
        schedule = (
            k8s.BatchV1beta1Api()
            .read_namespaced_cron_job(name, namespace)
            .spec.schedule
        )

    if project_repo_url and project_repo_branch:
        pod_spec = k8s.V1PodSpec(
            containers=[
                k8s.V1Container(
                    name="bodywork",
                    command=[
                        "bodywork",
                        "create",
                        "deployment",
                    ],
                    args=[project_repo_url, project_repo_branch],
                )
            ],
        )
        job = k8s.V1Job(
            spec=k8s.V1JobSpec(
                template=k8s.V1PodTemplateSpec(spec=pod_spec),
                backoff_limit=retries,
            )
        )
        job_template = k8s.V1beta1JobTemplateSpec(spec=job.spec)
    else:
        job_template = k8s.V1beta1JobTemplateSpec()

    cronjob = k8s.V1beta1CronJob(
        spec=k8s.V1beta1CronJobSpec(
            job_template=job_template,
            schedule=schedule,
            successful_jobs_history_limit=successful_jobs_history_limit,
            failed_jobs_history_limit=failed_jobs_history_limit,
        )
    )

    k8s.BatchV1beta1Api().patch_namespaced_cron_job(name, namespace, cronjob)


def delete_workflow_cronjob(namespace: str, name: str) -> None:
    """Delete a cron-job on a k8s cluster.

    :param namespace: Namespace in which to look for the cronjob to
        delete.
    :param name: The name of the cronjob to be deleted.
    """
    k8s.BatchV1beta1Api().delete_namespaced_cron_job(
        name=name,
        namespace=namespace,
        body=k8s.V1DeleteOptions(propagation_policy="Background"),
    )


def list_workflow_cronjobs(namespace: str) -> Dict[str, Dict[str, str]]:
    """Get all cronjobs and their high-level info.

    :param namespace: Namespace in which to list cronjobs.
    """
    cronjobs = k8s.BatchV1beta1Api().list_namespaced_cron_job(namespace=namespace)
    cronjob_info = {
        cronjob.metadata.name: {
            "schedule": cronjob.spec.schedule,
            "last_scheduled_time": cronjob.status.last_schedule_time,
            "retries": cronjob.spec.job_template.spec.backoff_limit,
            "git_url": (
                cronjob.spec.job_template.spec.template.spec.containers[0].args[0]
            ),
            "git_branch": (
                cronjob.spec.job_template.spec.template.spec.containers[0].args[1]
            ),
        }
        for cronjob in cronjobs.items
    }
    return cronjob_info


def list_workflow_jobs(
    namespace: str, job_name: str
) -> Dict[str, Dict[str, Union[datetime, bool]]]:
    """Get historic workflow jobs.

    Get status information for workflow jobs owned by a job or cronjob.

    :param namespace: Namespace in which to list workflow jobs.
    :param job_name: Name of job that triggered workflow job.
    :return: Dictionary of workflow jobs each mapping to a dictionary of
        status information fields for the workflow.
    """
    workflow_jobs_query = k8s.BatchV1Api().list_namespaced_job(namespace=namespace)
    workflow_jobs_info = {
        workflow_job.metadata.name: {
            "start_time": workflow_job.status.start_time,
            "completion_time": workflow_job.status.completion_time,
            "active": True if workflow_job.status.active else False,
            "succeeded": True if workflow_job.status.succeeded else False,
            "failed": True if workflow_job.status.failed else False,
        }
        for workflow_job in workflow_jobs_query.items
        if workflow_job.metadata.name.startswith(job_name)
    }
    return workflow_jobs_info
