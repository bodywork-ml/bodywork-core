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
This module contains all of the functions required to execute and manage
a Bodywork project workflow - a sequence of stages represented as a DAG.
"""
from pathlib import Path
from shutil import rmtree
from typing import cast, Tuple, List, Any
from kubernetes.client.exceptions import ApiException

import requests
import os
import stat

from . import k8s
from .cli.terminal import print_pod_logs
from .config import BodyworkConfig, BatchStageConfig, ServiceStageConfig
from .constants import (
    DEFAULT_PROJECT_DIR,
    PROJECT_CONFIG_FILENAME,
    TIMEOUT_GRACE_SECONDS,
    GIT_COMMIT_HASH_K8S_ENV_VAR,
    USAGE_STATS_SERVER_URL,
    FAILURE_EXCEPTION_K8S_ENV_VAR,
    BODYWORK_STAGES_SERVICE_ACCOUNT,
    BODYWORK_NAMESPACE,
    SSH_SECRET_NAME,
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
    repo_url: str,
    repo_branch: str = None,
    docker_image_override: str = None,
    config: BodyworkConfig = None,
    ssh_key_path: str = None,
    cloned_repo_dir: Path = DEFAULT_PROJECT_DIR,
) -> None:
    """Retrieve latest project code and run the workflow.

    :param repo_url: Git repository URL.
    :param repo_branch: The Git branch to download, defaults to None.
    :param docker_image_override: Docker image to use for executing all
        stages, that will override the one specified in the
        project config file. Provided purely for testing purposes and
        defaults to None.
    :param config: Override config.
    :param cloned_repo_dir: The name of the directory into which the
        repository will be cloned, defaults to DEFAULT_PROJECT_DIR.
    :param ssh_key_path:
    :raises BodyworkWorkflowExecutionError: if the workflow fails to
        run for any reason.
    """

    try:
        download_project_code_from_repo(
            repo_url, repo_branch, cloned_repo_dir, ssh_key_path
        )
        if config is None:
            config = BodyworkConfig(cloned_repo_dir / PROJECT_CONFIG_FILENAME, True)

        _log.setLevel(config.logging.log_level)
        namespace = _setup_namespace(config, repo_url)
        workflow_dag = config.pipeline.workflow
        all_stages = config.stages
        docker_image = (
            config.pipeline.docker_image
            if docker_image_override is None
            else docker_image_override
        )
        image_name, image_tag = parse_dockerhub_image_string(docker_image)
        if not image_exists_on_dockerhub(image_name, image_tag):
            msg = f"Cannot locate {image_name}:{image_tag} on DockerHub"
            raise BodyworkDockerImageError(msg)
        git_commit_hash = get_git_commit_hash(cloned_repo_dir)
        env_vars = k8s.create_k8s_environment_variables(
            [(GIT_COMMIT_HASH_K8S_ENV_VAR, git_commit_hash)]
        )
        secrets_group = config.pipeline.secrets_group
        if ssh_key_path:
            if not secrets_group:
                secrets_group = config.pipeline.name
            k8s.create_ssh_key_secret_from_file(secrets_group, Path(ssh_key_path))
        if secrets_group:
            if k8s.secret_exists(
                BODYWORK_NAMESPACE,
                k8s.create_complete_secret_name(secrets_group, SSH_SECRET_NAME),
            ):
                env_vars.append(k8s.create_secret_env_variable())
            _copy_secrets_to_target_namespace(namespace, secrets_group)
        elif k8s.secret_exists(
            BODYWORK_NAMESPACE,
            k8s.create_complete_secret_name(config.pipeline.name, SSH_SECRET_NAME),
        ):
            env_vars.append(k8s.create_secret_env_variable())
            _copy_secrets_to_target_namespace(namespace, config.pipeline.name)

        for step in workflow_dag:
            _log.info(f"Attempting to execute DAG step = [{', '.join(step)}]")
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
                    env_vars,
                    namespace,
                    repo_branch,
                    repo_url,
                    docker_image,
                )
            if service_stages:
                _run_service_stages(
                    service_stages,
                    config.pipeline.name,
                    env_vars,
                    namespace,
                    repo_branch,
                    repo_url,
                    docker_image,
                    git_commit_hash,
                )
            _log.info(f"Successfully executed DAG step = [{', '.join(step)}]")
        _log.info("Deployment successful")
        if not workflow_deploys_services(config):
            _log.info(f"Deleting namespace = {namespace}")
            k8s.delete_namespace(namespace)
        else:
            _cleanup_redundant_services(git_commit_hash, namespace)
        if config.pipeline.usage_stats:
            _ping_usage_stats_server()
    except Exception as e:
        msg = f"Deployment failed --> {e}"
        _log.error(msg)
        try:
            if (
                type(e)
                not in [
                    BodyworkNamespaceError,
                    BodyworkDockerImageError,
                    BodyworkGitError,
                    BodyworkConfigError,
                ]
                and config
                and config.pipeline.run_on_failure
            ):
                if config.pipeline.usage_stats:
                    _ping_usage_stats_server()
                _run_failure_stage(
                    config, e, namespace, repo_url, repo_branch, docker_image
                )
        except Exception as ex:
            failure_msg = (
                f"Error executing failure stage = {config.pipeline.run_on_failure} "  # type: ignore  # noqa
                f"after failed workflow : {ex}"
            )
            _log.error(failure_msg)
            msg = f"{msg}\n{failure_msg}"
        raise BodyworkWorkflowExecutionError(msg) from e
    finally:
        if cloned_repo_dir.exists():
            rmtree(cloned_repo_dir, onerror=_remove_readonly)


def _cleanup_redundant_services(git_commit_hash, namespace) -> None:
    """Deletes services that are not part of this git commit.

    :param git_commit_hash: Git commit hash of current deployment.
    :param namespace: Namespace deployment is in.
    """
    _log.info("Searching for services from previous deployment.")
    deployments = k8s.list_service_stage_deployments(namespace)
    for _, deployment in deployments.items():
        name = deployment["name"]
        if deployment["git_commit_hash"] != git_commit_hash:
            _log.info(
                f"Removing service: {name} from previous deployment with "
                f"git-commit-hash: {deployment['git_commit_hash']}."
            )
            k8s.delete_deployment(namespace, name)


def _setup_namespace(config: BodyworkConfig, repo_url: str) -> str:
    """Creates namespace to run workflow in.

    :param config: Bodywork config.
    :param config: Git repository URL.
    :return: Name of namespace.
    """
    namespace = str(
        config.pipeline.namespace if config.pipeline.namespace else config.pipeline.name
    )
    try:
        if not k8s.namespace_exists(namespace):
            _log.info(f"Creating k8s namespace = {namespace}")
            k8s.create_namespace(namespace)
        else:
            _log.info(f"Using k8s namespace = {namespace}")
            deployments = k8s.list_service_stage_deployments(namespace)
            for name, deployment in deployments.items():
                if deployment["git_url"] != repo_url:
                    raise BodyworkNamespaceError(
                        f"A project with the same name (or namespace): {namespace},"
                        " originating from a different git repository, has already "
                        "been deployed. Please choose another name."
                    )
        if not k8s.service_account_exists(namespace, BODYWORK_STAGES_SERVICE_ACCOUNT):
            _log.info(
                f"Creating k8s service account = {BODYWORK_STAGES_SERVICE_ACCOUNT}"
            )
            k8s.setup_stages_service_account(namespace)
        return namespace
    except ApiException as e:
        raise BodyworkNamespaceError(
            f"Unable to setup namespace: {namespace} - {e}"
        ) from e


def workflow_deploys_services(config: BodyworkConfig) -> bool:
    """Checks if any services are configured for deployment

    :param config: Bodywork config.
    :return: True if services are configured for deployment.
    """
    return any(
        True
        for stage_name, stage in config.stages.items()
        if isinstance(stage, ServiceStageConfig) and stage_name in config.pipeline.DAG
    )


def _run_batch_stages(
    batch_stages: List[BatchStageConfig],
    env_vars: List[k8s.EnvVars],
    namespace: str,
    repo_branch: str,
    repo_url: str,
    docker_image: str,
) -> None:
    """Run Batch Stages defined in the workflow.

    :param batch_stages: List of batch stages to execute.
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
        _log.info(f"Creating k8s job for stage = {job_name}")
        k8s.create_job(job_object)
    try:
        timeout = max(stage.max_completion_time for stage in batch_stages)
        k8s.monitor_jobs_to_completion(job_objects, timeout + TIMEOUT_GRACE_SECONDS)
    except TimeoutError as e:
        _log.error("Some (or all) k8s jobs failed to complete successfully")
        raise e
    finally:
        for job_object in job_objects:
            job_name = job_object.metadata.name
            _log.info(f"Completed k8s job for stage = {job_name}")
            _print_logs_to_stdout(namespace, job_name)
            _log.info(f"Deleting k8s job for stage = {job_name}")
            k8s.delete_job(namespace, job_name)
            _log.info(f"Deleted k8s job for stage = {job_name}")


def _run_service_stages(
    service_stages: List[ServiceStageConfig],
    project_name: str,
    env_vars: List[k8s.EnvVars],
    namespace: str,
    repo_branch: str,
    repo_url: str,
    docker_image: str,
    git_commit_hash: str,
) -> None:
    """Run Service Stages defined in the workflow.

    :param service_stages: List of service stages to execute.
    :param project_name: Project name
    :param env_vars: List of k8s environment variables to add.
    :param namespace: K8s namespace to execute the service stage in.
    :param repo_branch: The Git branch to download.
    :param repo_url: Git repository URL.
    :param docker_image: Docker Image to use.
    :param git_commit_hash: The git commit hash of this Bodywork project.
    """
    deployment_objects = [
        k8s.configure_service_stage_deployment(
            namespace,
            stage.name,
            project_name,
            repo_url,
            git_commit_hash,
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
            _log.info(f"Updating k8s deployment for stage = {deployment_name}")
            k8s.update_deployment(deployment_object)
        else:
            _log.info(
                f"Creating k8s deployment and service for stage = {deployment_name}"
            )
            k8s.create_deployment(deployment_object)
    try:
        timeout = max(stage.max_startup_time for stage in service_stages)
        k8s.monitor_deployments_to_completion(
            deployment_objects, timeout + TIMEOUT_GRACE_SECONDS
        )
    except TimeoutError as e:
        _log.error("Deployments failed to roll-out successfully")
        for deployment_object in deployment_objects:
            deployment_name = deployment_object.metadata.name
            _print_logs_to_stdout(namespace, deployment_name)
            _log.info(f"Rolling-back k8s deployment for stage = {deployment_name}")
            k8s.rollback_deployment(deployment_object)
            _log.info(f"Rolled-back k8s deployment for stage = {deployment_name}")
        raise e

    for deployment_object, stage in zip(deployment_objects, service_stages):
        deployment_name = deployment_object.metadata.name
        deployment_port = deployment_object.metadata.annotations["port"]
        _log.info(f"Successfully created k8s deployment for stage = {deployment_name}")
        _print_logs_to_stdout(namespace, deployment_name)
        if not k8s.is_exposed_as_cluster_service(namespace, deployment_name):
            _log.info(
                f"Exposing stage = {deployment_name} as a k8s service at "
                f"http://{deployment_name}.{namespace}.svc.cluster"
                f".local:{deployment_port}"
            )
            k8s.expose_deployment_as_cluster_service(deployment_object)
        if not k8s.has_ingress(namespace, deployment_name) and stage.create_ingress:
            _log.info(
                f"Creating k8s ingress for stage = {deployment_name} at "
                f"path = /{namespace}/{deployment_name}"
            )
            k8s.create_deployment_ingress(deployment_object)
        if k8s.has_ingress(namespace, deployment_name) and not stage.create_ingress:
            _log.info(
                f"Deleting k8s ingress for stage = {deployment_name} at "
                f"path = /{namespace}/{deployment_name}"
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
    stage_name = config.pipeline.run_on_failure
    _log.info(f"Executing stage = {stage_name}")
    stage = [cast(BatchStageConfig, config.stages[stage_name])]
    env_vars = k8s.create_k8s_environment_variables(
        [(FAILURE_EXCEPTION_K8S_ENV_VAR, str(workflow_exception))]
    )
    _run_batch_stages(
        stage,
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
        f"Invalid Docker image specified: {image_string} - "
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
        if pod_name is not None:
            pod_logs = k8s.get_pod_logs(namespace, pod_name)
            print_pod_logs(pod_logs, f"logs for stage = {pod_name}")
        else:
            _log.warning(f"Cannot get logs for {job_or_deployment_name}")
    except Exception:
        _log.warning(f"Cannot get logs for {job_or_deployment_name}")


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


def _copy_secrets_to_target_namespace(namespace: str, secrets_group: str) -> None:
    """Copies secrets from a specific group to the specified namespace.

    param namespace: Namespace to copy secrets to.
    param secrets_group: Group of secrets to copy.
    """
    try:
        _log.info(
            f"Replicating k8s secrets from group = {secrets_group} into "
            f"namespace = {namespace}"
        )
        k8s.replicate_secrets_in_namespace(namespace, secrets_group)
    except ApiException as e:
        _log.error(
            f"Unable to replicate k8s secrets from group = {secrets_group} into "
            f"namespace = {namespace}"
        )
        raise e
