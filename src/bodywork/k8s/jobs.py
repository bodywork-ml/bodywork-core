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
High-level interface to the Kubernetes batch API as used to create and
manage Bodywork batch stages.
"""
from enum import Enum
from time import sleep, time
from typing import Iterable, List, Optional

from kubernetes import client as k8s

from ..constants import (
    BODYWORK_DOCKER_IMAGE,
    BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT,
    SSH_GITHUB_KEY_ENV_VAR,
    SSH_GITHUB_SECRET_NAME
)
from ..exceptions import BodyworkJobFailure


class JobStatus(Enum):
    "Possible states of a k8s job."

    ACTIVE = 'active'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


def configure_batch_stage_job(
    namespace: str,
    stage_name: str,
    project_name: str,
    project_repo_url: str,
    project_repo_branch: str = 'master',
    image: str = BODYWORK_DOCKER_IMAGE,
    retries: int = 2,
    container_env_vars: Optional[List[k8s.V1EnvVar]] = None,
    cpu_request: Optional[float] = None,
    memory_request: Optional[int] = None
) -> k8s.V1Job:
    """Configure a Bodywork batch stage k8s job.

    :param namespace: The k8s namespace to target deployment.
    :param stage_name: The name of the Bodywork project stage that
        will need to be executed.
    :param project_name: The name of the Bodywork project that the stage
        belongs to.
    :param project_repo_url: The URL for the Bodywork project Git
        repository.
    :param project_repo_branch: The Bodywork project Git repository
        branch to use, defaults to 'master'.
    :param image: Docker image to use for running the stage within,
        defaults to BODYWORK_DOCKER_IMAGE.
    :param retries: Number of times to retry running the stage to
        completion (if necessary), defaults to 2.
    :param container_env_vars: Optional list of environment variables
        (e.g. secrets) to set in the container, defaults to None.
    :param cpu_request: CPU resource to request from a node, expressed
        as a decimal number, defaults to None.
    :param memory_request: Memory resource to request from a node, expressed
        as an integer number of megabytes, defaults to None.
    :return: A configured k8s job object.
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
    env_vars = vcs_env_vars + container_env_vars if container_env_vars else vcs_env_vars
    container_resources = k8s.V1ResourceRequirements(
        requests={
            'cpu': f'{cpu_request}' if cpu_request else None,
            'memory': f'{memory_request}M' if memory_request else None
        }
    )
    container = k8s.V1Container(
        name='bodywork',
        image=image,
        image_pull_policy='Always',
        resources=container_resources,
        env=env_vars,
        command=['bodywork', 'stage'],
        args=[project_repo_url, project_repo_branch, stage_name]
    )
    pod_spec = k8s.V1PodSpec(
        service_account_name=BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT,
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
    job_metadata = k8s.V1ObjectMeta(
        namespace=namespace,
        name=f'{project_name}--{stage_name}'
    )
    job = k8s.V1Job(
        metadata=job_metadata,
        spec=job_spec
    )
    return job


def create_job(job: k8s.V1Job) -> None:
    """Create a job on a k8s cluster.

    :param job: A configured job object.
    """
    k8s.BatchV1Api().create_namespaced_job(
        body=job,
        namespace=job.metadata.namespace
    )


def delete_job(namespace: str, name: str) -> None:
    """Delete a job on a k8s cluster.

    :param namespace: Namespace in which to look for the job to
        delete.
    :param name: The name of the job to be deleted.
    """
    k8s.BatchV1Api().delete_namespaced_job(
        name=name,
        namespace=namespace,
        body=k8s.V1DeleteOptions(propagation_policy='Background')
    )


def _get_job_status(job: k8s.V1Job) -> JobStatus:
    """Get the latest status of a job created on a k8s cluster.

    :param job: A configured job object.
    :raises RuntimeError: If the job cannot be found or the status
        cannot be identified.
    :return: The current status of the job.
    """
    try:
        k8s_job_query = k8s.BatchV1Api().list_namespaced_job(
            namespace=job.metadata.namespace,
            field_selector=f'metadata.name={job.metadata.name}'
        )
        k8s_job_data = k8s_job_query.items[0]
    except IndexError as e:
        msg = (f'cannot find job={job.metadata.name} in '
               f'namespace={job.metadata.namespace}')
        raise RuntimeError(msg) from e

    if k8s_job_data.status.active == 1:
        return JobStatus.ACTIVE
    elif k8s_job_data.status.succeeded == 1:
        return JobStatus.SUCCEEDED
    elif k8s_job_data.status.failed == 1:
        return JobStatus.FAILED
    else:
        msg = (f'cannot determine status for job={job.metadata.name} in '
               f'namespace={job.metadata.namespace}')
        raise RuntimeError(msg)


def monitor_jobs_to_completion(
    jobs: Iterable[k8s.V1Job],
    timeout_seconds: int = 10,
    polling_freq_seconds: int = 1,
    wait_before_start_seconds: int = 5
) -> bool:
    """Monitor job status until completion or timeout.

    :param jobs: The jobs to monitor.
    :param timeout_seconds: How long to keep monitoring status before
        calling a timeout, defaults to 10.
    :param polling_freq_seconds: Time between status polling, defaults
        to 1.
    :param wait_before_start_seconds: Time to wait before starting to
        monitor jobs - e.g. to allow jobs to be created.
    :raises TimeoutError: If the timeout limit is reached and the jobs
        are still marked as active (but not failed).
    :raises BodyworkJobFailure: If any of the jobs are marked as
        failed.
    :return: True if all of the jobs complete successfully.
    """
    sleep(wait_before_start_seconds)
    start_time = time()
    jobs_status = [_get_job_status(job) for job in jobs]
    while any(job_status is JobStatus.ACTIVE for job_status in jobs_status):
        sleep(polling_freq_seconds)
        if time() - start_time >= timeout_seconds:
            unsuccessful_jobs_msg = [
                f'job={job.metadata.name} in namespace={job.metadata.namespace}'
                for job, status in zip(jobs, jobs_status)
                if status != JobStatus.SUCCEEDED
            ]
            msg = (f'{"; ".join(unsuccessful_jobs_msg)} have yet to reach '
                   f'status=succeeded after {timeout_seconds}s')
            raise TimeoutError(msg)
        jobs_status = [_get_job_status(job) for job in jobs]
    if any(job_status is JobStatus.FAILED for job_status in jobs_status):
        failed_jobs = [
            job
            for job, status in zip(jobs, jobs_status)
            if status == JobStatus.FAILED
        ]
        if len(failed_jobs) > 0:
            raise BodyworkJobFailure(failed_jobs)
    return True
