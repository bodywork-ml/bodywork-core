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
This module contains all of the functions required to execute and manage
a Bodywork project workflow - a sequence of stages represented as a DAG.
"""
from pathlib import Path
from shutil import rmtree
from typing import cast, Optional, Tuple, List, Any
from kubernetes.client.exceptions import ApiException

import requests
import os
import stat

from . import k8s
from .config import BodyworkConfig, BatchStageConfig, ServiceStageConfig
from .constants import (
    DEFAULT_PROJECT_DIR,
    PROJECT_CONFIG_FILENAME,
    TIMEOUT_GRACE_SECONDS,
    GIT_COMMIT_HASH_K8S_ENV_VAR,
    USAGE_STATS_SERVER_URL,
    FAILURE_EXCEPTION_K8S_ENV_VAR,
)
from .exceptions import (
    BodyworkWorkflowExecutionError,
    BodyworkNamespaceError,
    BodyworkDockerImageError,
    BodyworkGitError,
    BodyworkConfigError,
)
from .git import download_project_code_from_repo, get_git_commit_hash
from .logs import bodywork_log_factory

_log = bodywork_log_factory()


def run_workflow(
    namespace: str,
    repo_url: str,
    repo_branch: str = "master",
    docker_image_override: Optional[str] = None,
    config_override: Optional[BodyworkConfig] = None,
    cloned_repo_dir: Path = DEFAULT_PROJECT_DIR,
) -> None:
    """Retrieve latest project code and run the workflow.

    :param namespace: Kubernetes namespace to execute the workflow in.
    :param repo_url: Git repository URL.
    :param repo_branch: The Git branch to download, defaults to 'master'.
    :param docker_image_override: Docker image to use for executing all
        stages, that will override the one specified in the
        project config file. Provided purely for testing purposes and
        defaults to None.
    :param config_override: Configuration data for the Bodywork deployment.
    :param cloned_repo_dir: The name of the directory into which the
        repository will be cloned, defaults to DEFAULT_PROJECT_DIR.
    :raises BodyworkWorkflowExecutionError: if the workflow fails to
        run for any reason.
    """
    try:
        _log.info(
            f"attempting to run workflow for project={repo_url} on "
            f"branch={repo_branch} in kubernetes namespace={namespace}"
        )
        download_project_code_from_repo(repo_url, repo_branch, cloned_repo_dir)
        config = (
            config_override
            if config_override is not None
            else BodyworkConfig(cloned_repo_dir / PROJECT_CONFIG_FILENAME, True)
        )
        _log.setLevel(config.logging.log_level)
        try:
            if k8s.namespace_exists(namespace) is False:
                raise BodyworkNamespaceError(
                    f"{namespace} is not a valid namespace on your cluster."
                )
        except ApiException as e:
            raise BodyworkNamespaceError(
                f"Unable to check namespace: {namespace} : {e}"
            ) from e

        workflow_dag = config.project.workflow
        all_stages = config.stages
        docker_image = (
            config.project.docker_image
            if docker_image_override is None
            else docker_image_override
        )
        image_name, image_tag = parse_dockerhub_image_string(docker_image)
        if not image_exists_on_dockerhub(image_name, image_tag):
            msg = f"cannot locate {image_name}:{image_tag} on DockerHub"
            raise BodyworkDockerImageError(msg)
        env_vars = k8s.create_k8s_environment_variables(
            [(GIT_COMMIT_HASH_K8S_ENV_VAR, get_git_commit_hash(cloned_repo_dir))]
        )
        for step in workflow_dag:
            _log.info(f"attempting to execute DAG step={step}")
            batch_stages = [
                cast(BatchStageConfig, all_stages[stage_name])
                for stage_name in step
                if type(all_stages[stage_name]) is BatchStageConfig
            ]
            service_stages = [
                cast(ServiceStageConfig, all_stages[stage_name])
                for stage_name in step
                if type(all_stages[stage_name]) is ServiceStageConfig
            ]
            if batch_stages:
                _run_batch_stages(
                    batch_stages,
                    config.project.name,
                    env_vars,
                    namespace,
                    repo_branch,
                    repo_url,
                    docker_image,
                )
            if service_stages:
                _run_service_stages(
                    service_stages,
                    config.project.name,
                    env_vars,
                    namespace,
                    repo_branch,
                    repo_url,
                    docker_image,
                )
            _log.info(f"successfully executed DAG step={step}")
        _log.info(
            f"successfully ran workflow for project={repo_url} on "
            f"branch={repo_branch} in kubernetes namespace={namespace}"
        )
    except Exception as e:
        msg = (
            f"failed to execute workflow for {repo_branch} branch of project "
            f"repository at {repo_url}: {e}"
        )
        _log.error(msg)
        try:
            if config.project.run_on_failure and type(e) not in [
                BodyworkNamespaceError,
                BodyworkDockerImageError,
                BodyworkGitError,
                BodyworkConfigError,
            ]:
                _run_failure_stage(
                    config, e, namespace, repo_url, repo_branch, docker_image
                )
        except Exception as ex:
            failure_msg = (
                f"Error executing failure stage: {config.project.run_on_failure}"
                f" after failed workflow : {ex}"
            )
            _log.error(failure_msg)
            msg = f"{msg}\n{failure_msg}"
        raise BodyworkWorkflowExecutionError(msg) from e
    finally:
        if cloned_repo_dir.exists():
            rmtree(cloned_repo_dir, onerror=_remove_readonly)
        if config is not None and config.project.usage_stats:
            _ping_usage_stats_server()


def _run_batch_stages(
    batch_stages: List[BatchStageConfig],
    project_name: str,
    env_vars: k8s.EnvVars,
    namespace: str,
    repo_branch: str,
    repo_url: str,
    docker_image: str,
) -> None:
    """Run Batch Stages defined in the workflow.

    :param batch_stages: List of batch stages to execute.
    :param project_name: Project name
    :param env_vars: List of k8s environment variables to add.
    :param namespace: K8s namespace to execute the batch stage in.
    :param repo_branch: The Git branch to download'.
    :param repo_url: Git repository URL.
    :param docker_image: Docker Image to use.
    """
    job_objects = [
        k8s.configure_batch_stage_job(
            namespace,
            stage.name,
            project_name,
            repo_url,
            repo_branch,
            retries=stage.retries,
            container_env_vars=k8s.configure_env_vars_from_secrets(
                namespace, stage.env_vars_from_secrets
            )
            + env_vars,
            image=docker_image,
            cpu_request=stage.cpu_request,
            memory_request=stage.memory_request,
        )
        for stage in batch_stages
    ]
    for job_object in job_objects:
        job_name = job_object.metadata.name
        _log.info(f"creating job={job_name} in namespace={namespace}")
        k8s.create_job(job_object)
    try:
        timeout = max(stage.max_completion_time for stage in batch_stages)
        k8s.monitor_jobs_to_completion(job_objects, timeout + TIMEOUT_GRACE_SECONDS)
    finally:
        for job_object in job_objects:
            job_name = job_object.metadata.name
            _log.info(f"completed job={job_name} from namespace={namespace}")
            _print_logs_to_stdout(namespace, job_name)
            _log.info(f"deleting job={job_name} from namespace={namespace}")
            k8s.delete_job(namespace, job_name)
            _log.info(f"deleted job={job_name} from namespace={namespace}")


def _run_service_stages(
    service_stages: List[ServiceStageConfig],
    project_name: str,
    env_vars: k8s.EnvVars,
    namespace: str,
    repo_branch: str,
    repo_url: str,
    docker_image: str,
) -> None:
    """Run Service Stages defined in the workflow.

    :param service_stages: List of service stages to execute.
    :param project_name: Project name
    :param env_vars: List of k8s environment variables to add.
    :param namespace: K8s namespace to execute the service stage in.
    :param repo_branch: The Git branch to download.
    :param repo_url: Git repository URL.
    :param docker_image: Docker Image to use.
    """
    deployment_objects = [
        k8s.configure_service_stage_deployment(
            namespace,
            stage.name,
            project_name,
            repo_url,
            repo_branch,
            replicas=stage.replicas,
            port=stage.port,
            container_env_vars=k8s.configure_env_vars_from_secrets(
                namespace, stage.env_vars_from_secrets
            )
            + env_vars,
            image=docker_image,
            cpu_request=stage.cpu_request,
            memory_request=stage.memory_request,
            seconds_to_be_ready_before_completing=stage.max_startup_time,
        )
        for stage in service_stages
    ]
    for deployment_object in deployment_objects:
        deployment_name = deployment_object.metadata.name
        if k8s.is_existing_deployment(namespace, deployment_name):
            _log.info(
                f"updating deployment={deployment_name} in " f"namespace={namespace}"
            )
            k8s.update_deployment(deployment_object)
        else:
            _log.info(
                f"creating deployment={deployment_name} in " f"namespace={namespace}"
            )
            k8s.create_deployment(deployment_object)
    try:
        timeout = max(stage.max_startup_time for stage in service_stages)
        k8s.monitor_deployments_to_completion(
            deployment_objects, timeout + TIMEOUT_GRACE_SECONDS
        )
    except TimeoutError as e:
        _log.error("deployments failed to roll-out successfully")
        for deployment_object in deployment_objects:
            deployment_name = deployment_object.metadata.name
            _print_logs_to_stdout(namespace, deployment_name)
            _log.info(
                f"rolling back deployment={deployment_name} in "
                f"namespace={namespace}"
            )
            k8s.rollback_deployment(deployment_object)
            _log.info(
                f"rolled back deployment={deployment_name} in " f"namespace={namespace}"
            )
        raise e

    for deployment_object, stage in zip(deployment_objects, service_stages):
        deployment_name = deployment_object.metadata.name
        deployment_port = deployment_object.metadata.annotations["port"]
        _log.info(
            f"successful deployment={deployment_name} in " f"namespace={namespace}"
        )
        _print_logs_to_stdout(namespace, deployment_name)
        if not k8s.is_exposed_as_cluster_service(namespace, deployment_name):
            _log.info(
                f"exposing deployment={deployment_name} in "
                f"namespace={namespace} at"
                f"http://{deployment_name}.{namespace}.svc.cluster"
                f".local:{deployment_port}"
            )
            k8s.expose_deployment_as_cluster_service(deployment_object)
        if not k8s.has_ingress(namespace, deployment_name) and stage.create_ingress:
            _log.info(
                f"creating ingress for deployment={deployment_name} in "
                f"namespace={namespace} with"
                f"path=/{namespace}/{deployment_name}"
            )
            k8s.create_deployment_ingress(deployment_object)
        if k8s.has_ingress(namespace, deployment_name) and not stage.create_ingress:
            _log.info(
                f"deleting ingress for deployment={deployment_name} in "
                f"namespace={namespace} with"
                f"path=/{namespace}/{deployment_name}"
            )
            k8s.delete_deployment_ingress(namespace, deployment_name)


def _run_failure_stage(
    config: BodyworkConfig,
    workflow_exception: Exception,
    namespace: str,
    repo_url: str,
    repo_branch: str,
    docker_image: str,
) -> None:
    """Runs the configured Batch Stage if the workflow fails.
    :param config: Configuration data for the Bodywork deployment.
    :param workflow_exception: Exception from workflow f
    :param namespace: K8s namespace to execute the service stage in.
    :param repo_url: Git repository URL.
    :param repo_branch: The Git branch to download.
    :param docker_image: Docker Image to use.
    """
    stage_name = config.project.run_on_failure
    _log.info(f"Executing Stage: {stage_name}")
    stage = [cast(BatchStageConfig, config.stages[stage_name])]
    env_vars = k8s.create_k8s_environment_variables(
        [(FAILURE_EXCEPTION_K8S_ENV_VAR, str(workflow_exception))]
    )
    _run_batch_stages(
        stage,
        config.project.name,
        env_vars,
        namespace,
        repo_branch,
        repo_url,
        docker_image,
    )


def image_exists_on_dockerhub(repo_name: str, tag: str) -> bool:
    """Check DockerHub to see if named Bodywork image exists.

    :param repo_name: The name of the DockerHub repository containing
        the Bodywork images.
    :param tag: The specific image tag to check.
    :raises BodyworkDockerImageError: If connection to DockerHub fails.
    :return: Boolean flag for image existence on DockerHub.
    """
    dockerhub_url = f"https://hub.docker.com/v2/repositories/{repo_name}/tags/{tag}"
    try:
        session = requests.Session()
        session.mount(dockerhub_url, requests.adapters.HTTPAdapter(max_retries=3))
        response = session.get(dockerhub_url)
        if response.ok:
            return True
        else:
            return False
    except requests.exceptions.ConnectionError as e:
        msg = f"cannot connect to {dockerhub_url} to check image exists"
        raise BodyworkDockerImageError(msg) from e


def parse_dockerhub_image_string(image_string: str) -> Tuple[str, str]:
    """Split a DockerHub image string into name and tag.

    :param image_string: The DockerHub image string to parse.
    :raises BodyworkDockerImageError: If the string is not in the
        DOCKERHUB_USERNAME/IMAGE_NAME:TAG format.
    :return: Image name and image tag tuple.
    """
    err_msg = (
        f"invalid DOCKER_IMAGE specified in {PROJECT_CONFIG_FILENAME} file - "
        f"cannot be parsed as DOCKERHUB_USERNAME/IMAGE_NAME:TAG"
    )
    if len(image_string.split("/")) != 2:
        raise BodyworkDockerImageError(err_msg)
    parsed_image_string = image_string.split(":")
    if len(parsed_image_string) == 2:
        image_name = parsed_image_string[0]
        image_tag = parsed_image_string[1]
    elif len(parsed_image_string) == 1:
        image_name = parsed_image_string[0]
        image_tag = "latest"
    else:
        raise BodyworkDockerImageError(err_msg)
    return image_name, image_tag


def _print_logs_to_stdout(namespace: str, job_or_deployment_name: str) -> None:
    """Replay pod logs from a job or deployment to stdout.

    :param namespace: The namespace the job/deployment is in.
    :param job_or_deployment_name: The name of the pod or deployment.
    """
    try:
        pod_name = k8s.get_latest_pod_name(namespace, job_or_deployment_name)
        print("-" * 100)
        print(f"---- pod logs for {job_or_deployment_name}")
        print("-" * 100)
        if pod_name is not None:
            pod_logs = k8s.get_pod_logs(namespace, pod_name)
            print(pod_logs)
        else:
            print(f"cannot get logs for {job_or_deployment_name}")
        print("-" * 100)
        print("-" * 100)
    except Exception:
        print(f"cannot get logs for {job_or_deployment_name}")


def _remove_readonly(func: Any, path: Any, exc_info: Any) -> None:
    """Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file) it
    attempts to add write permission and then retries. If the error is
    for another reason it re-raises the error. This is primarily to
    fix Windows OS access issues.

    Usage: ``shutil.rmtree(path, onerror=_remove_readonly)``
    """
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        _log.warning(f"Could not remove file/directory: {path}")


def _ping_usage_stats_server() -> None:
    """Pings the usage stats server."""
    try:
        session = requests.Session()
        session.mount(
            USAGE_STATS_SERVER_URL, requests.adapters.HTTPAdapter(max_retries=0)
        )
        response = session.get(USAGE_STATS_SERVER_URL, params={"type": "workflow"})
        if not response.ok:
            _log.info("Unable to contact usage stats server")
    except requests.exceptions.RequestException:
        _log.info("Unable to contact usage stats server")
