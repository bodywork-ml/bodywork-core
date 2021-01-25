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
from typing import cast, Dict, Iterable, Optional, Tuple, Union

import requests

from . import k8s
from .config import BodyworkConfig
from .constants import (
    DEFAULT_PROJECT_DIR,
    PROJECT_CONFIG_FILENAME,
    TIMEOUT_GRACE_SECONDS
)
from .exceptions import BodyworkProjectConfigError, BodyworkWorkflowExecutionError
from .git import download_project_code_from_repo
from .logs import bodywork_log_factory
from .stage import BatchStage, ServiceStage, Stage, stage_factory

DAG = Iterable[Iterable[str]]


class BodyworkProject:
    """Class for Bodywork project data."""

    def __init__(self, path_to_config_file: Path):
        """Constructor.

        :param path_to_config_file: Path to project config file.
        :raises BodyworkProjectConfigError: If mandatory project
            parameters have not been set: PROJECT_NAME, DAG and
            LOG_LEVEL.
        """
        project_config = BodyworkConfig(path_to_config_file)
        try:
            project_name = project_config['default']['PROJECT_NAME'].lower()
            docker_image = project_config['default']['DOCKER_IMAGE'].lower()
            dag = project_config['workflow']['DAG']
            log_level = project_config['logging']['LOG_LEVEL']
        except KeyError as e:
            raise BodyworkProjectConfigError(str(e)) from e

        self.name = project_name
        self.docker_image = docker_image
        self.dag = dag
        self.log_level = log_level


def run_workflow(
    namespace: str,
    repo_url: str,
    repo_branch: str = 'master',
    cloned_repo_dir: Path = DEFAULT_PROJECT_DIR,
    docker_image_override: Optional[str] = None
) -> None:
    """Retreive latest project code and run the workflow.

    :param namespace: Kubernetes namespace to execute the workflow in.
    :param repo_url: Git repository URL.
    :param repo_branch: The Git branch to download, defaults to 'master'.
    :param cloned_repo_dir: The name of the directory into which the
        repository will be cloned, defaults to DEFAULT_PROJECT_DIR.
    :param docker_image_override: Docker image to use for executing all
        stages, that will override the one specified in the
        project config file. Provided purely for testing purposes and
        defaults to None.
    :raises BodyworkWorkflowExecutionError: if the workflow fails to
        run for any reason.
    """
    try:
        log = bodywork_log_factory()
        log.info(f'attempting to run workflow for project={repo_url} on '
                 f'branch={repo_branch} in kubernetes namespace={namespace}')
        if k8s.namespace_exists(namespace) is False:
            raise ValueError(f'{namespace} is not a valid namespace on your cluster')
        download_project_code_from_repo(repo_url, repo_branch, cloned_repo_dir)
        path_to_project_config_file = cloned_repo_dir / PROJECT_CONFIG_FILENAME
        project = BodyworkProject(path_to_project_config_file)
        log.setLevel(project.log_level)

        workflow_dag = _parse_dag_definition(project.dag)
        all_stages = _get_workflow_stages(workflow_dag, cloned_repo_dir)

        docker_image = (
            project.docker_image
            if docker_image_override is None
            else docker_image_override
        )
        image_name, image_tag = parse_dockerhub_image_string(docker_image)
        if not image_exists_on_dockerhub(image_name, image_tag):
            msg = f'cannot locate {image_name}:{image_tag} on DockerHub'
            raise RuntimeError(msg)

        for step in workflow_dag:
            log.info(f'attempting to execute DAG step={step}')
            batch_stages = [
                cast(BatchStage, all_stages[stage_name])
                for stage_name in step
                if type(all_stages[stage_name]) is BatchStage
            ]
            service_stages = [
                cast(ServiceStage, all_stages[stage_name])
                for stage_name in step
                if type(all_stages[stage_name]) is ServiceStage
            ]

            if batch_stages:
                job_objects = [
                    k8s.configure_batch_stage_job(
                        namespace,
                        stage.name,
                        project.name,
                        repo_url,
                        repo_branch,
                        retries=stage.retries,
                        container_env_vars=k8s.configure_env_vars_from_secrets(
                            namespace,
                            stage.env_vars_from_secrets
                        ),
                        image=docker_image,
                        cpu_request=stage.cpu_request,
                        memory_request=stage.memory_request
                    )
                    for stage in batch_stages
                ]
                for job_object in job_objects:
                    job_name = job_object.metadata.name
                    log.info(f'creating job={job_name} in namespace={namespace}')
                    k8s.create_job(job_object)
                try:
                    timeout = max(stage.max_completion_time for stage in batch_stages)
                    k8s.monitor_jobs_to_completion(
                        job_objects,
                        timeout + TIMEOUT_GRACE_SECONDS
                    )
                finally:
                    for job_object in job_objects:
                        job_name = job_object.metadata.name
                        log.info(f'completed job={job_name} from namespace={namespace}')
                        _print_logs_to_stdout(namespace, job_name)
                        log.info(f'deleting job={job_name} from namespace={namespace}')
                        k8s.delete_job(namespace, job_name)
                        log.info(f'deleted job={job_name} from namespace={namespace}')

            if service_stages:
                deployment_objects = [
                    k8s.configure_service_stage_deployment(
                        namespace,
                        stage.name,
                        project.name,
                        repo_url,
                        repo_branch,
                        replicas=stage.replicas,
                        port=stage.port,
                        container_env_vars=k8s.configure_env_vars_from_secrets(
                            namespace,
                            stage.env_vars_from_secrets
                        ),
                        image=docker_image,
                        cpu_request=stage.cpu_request,
                        memory_request=stage.memory_request,
                        seconds_to_be_ready_before_completing=stage.max_startup_time
                    )
                    for stage in service_stages
                ]
                for deployment_object in deployment_objects:
                    deployment_name = deployment_object.metadata.name
                    if k8s.is_existing_deployment(namespace, deployment_name):
                        log.info(f'updating deployment={deployment_name} in '
                                 f'namespace={namespace}')
                        k8s.update_deployment(deployment_object)
                    else:
                        log.info(f'creating deployment={deployment_name} in '
                                 f'namespace={namespace}')
                        k8s.create_deployment(deployment_object)
                try:
                    timeout = max(stage.max_startup_time for stage in service_stages)
                    k8s.monitor_deployments_to_completion(
                        deployment_objects,
                        timeout + TIMEOUT_GRACE_SECONDS
                    )
                except TimeoutError as e:
                    log.error('deployments failed to roll-out successfully')
                    for deployment_object in deployment_objects:
                        deployment_name = deployment_object.metadata.name
                        _print_logs_to_stdout(namespace, deployment_name)
                        log.info(f'rolling back deployment={deployment_name} in '
                                 f'namespace={namespace}')
                        k8s.rollback_deployment(deployment_object)
                        log.info(f'rolled back deployment={deployment_name} in '
                                 f'namespace={namespace}')
                    raise e

                for deployment_object in deployment_objects:
                    deployment_name = deployment_object.metadata.name
                    deployment_port = deployment_object.metadata.annotations['port']
                    log.info(f'successful deployment={deployment_name} in '
                             f'namespace={namespace}')
                    _print_logs_to_stdout(namespace, deployment_name)
                    if not k8s.is_exposed_as_cluster_service(namespace, deployment_name):
                        log.info(f'exposing deployment={deployment_name} in '
                                 f'namespace={namespace} at'
                                 f'http://{deployment_name}.{namespace}.svc.cluster'
                                 f'.local:{deployment_port}')
                        k8s.expose_deployment_as_cluster_service(deployment_object)

            log.info(f'successfully executed DAG step={step}')
        log.info(f'successfully ran workflow for project={repo_url} on '
                 f'branch={repo_branch} in kubernetes namespace={namespace}')

    except Exception as e:
        msg = (f'failed to execute workflow for {repo_branch} branch of project '
               f'reposotory at {repo_url}: {e}')
        log.error(msg)
        raise BodyworkWorkflowExecutionError(msg) from e
    finally:
        if cloned_repo_dir.exists():
            rmtree(cloned_repo_dir)


def image_exists_on_dockerhub(repo_name: str, tag: str) -> bool:
    """Check DockerHub to see if named Bodywork image exists.

    :param repo_name: The name of the DockerHub repository containing
        the Bodywork images.
    :param tag: The specific image tag to check.
    :raises RuntimeError: If connection to DockerHub fails.
    :return: Boolean flag for image existence on DockerHub.
    """
    dockerhub_url = f'https://hub.docker.com/v2/repositories/{repo_name}/tags/{tag}'
    try:
        session = requests.Session()
        session.mount(dockerhub_url, requests.adapters.HTTPAdapter(max_retries=3))
        response = session.get(dockerhub_url)
        if response.ok:
            return True
        else:
            return False
    except requests.exceptions.ConnectionError as e:
        msg = f'cannot connect to {dockerhub_url} to check image exists'
        raise RuntimeError(msg) from e


def parse_dockerhub_image_string(image_string: str) -> Tuple[str, str]:
    """Split a DockerHub image string into name and tag.

    :param image_string: The DockerHub image string to parse.
    :raises ValueError: If the string is not in the
        DOCKERHUB_USERNAME/IMAGE_NAME:TAG format.
    :return: Image name and image tag tuple.
    """
    err_msg = (f'invalid DOCKER_IMAGE specified in {PROJECT_CONFIG_FILENAME} file - '
               f'cannot be parsed as DOCKERHUB_USERNAME/IMAGE_NAME:TAG')
    if len(image_string.split('/')) != 2:
        raise ValueError(err_msg)
    parsed_image_string = image_string.split(':')
    if len(parsed_image_string) == 2:
        image_name = parsed_image_string[0]
        image_tag = parsed_image_string[1]
    elif len(parsed_image_string) == 1:
        image_name = parsed_image_string[0]
        image_tag = 'latest'
    else:
        raise ValueError(err_msg)
    return image_name, image_tag


def _parse_dag_definition(dag_definition: str) -> DAG:
    """Parse DAG definition string.

    :param dag_definition: A DAG definition in string format.
    :raises ValueError: If any 'null' (zero character) stage names are
        found.
    :return: A list of steps, where each step is a list of Bodywork
        project stage names (containing a list of stages to run in each
        step).
    """
    steps = dag_definition.replace(' ', '').split('>>')
    stages_in_steps = [step.split(',') for step in steps]
    steps_with_null_stages = [
        str(n)
        for n, step in enumerate(stages_in_steps, start=1) for stage in step
        if stage == ''
    ]
    if len(steps_with_null_stages) > 0:
        msg = (f'null stages found in step {", ".join(steps_with_null_stages)} when '
               f'parsing DAG definition')
        raise ValueError(msg)
    return stages_in_steps


def _get_workflow_stages(
    dag: DAG,
    cloned_repo_dir: Path = DEFAULT_PROJECT_DIR
) -> Dict[str, Stage]:
    """Ensure every stage in a DAG is executable.

    :param dag: The steps and stages to be executed.
    :param cloned_repo_dir: The name of the directory into which the
        repository has been cloned, defaults to DEFAULT_PROJECT_DIR.
    :raises: RuntimeError if any of the directories for the requested
        stages are not valid Bodywork stages.
    """
    def try_to_get_stage(stage_name: str) -> Union[Stage, Exception]:
        try:
            path_to_stage_dir = cloned_repo_dir / stage_name
            stage_info = stage_factory(path_to_stage_dir)
            return stage_info
        except Exception as e:
            return e

    attempted_stage_constructions = {
        stage: try_to_get_stage(stage)
        for step in dag
        for stage in step
    }

    invalid_stages = [
        str(stage)
        for stage in attempted_stage_constructions.values()
        if isinstance(stage, Exception)
    ]
    if invalid_stages:
        msg = (f'invaid stages found in Bodywork project repo: '
               f'{"; ".join(invalid_stages)}')
        raise RuntimeError(msg)
    else:
        valid_stages = cast(Dict[str, Stage], attempted_stage_constructions)
        return valid_stages


def _print_logs_to_stdout(namespace: str, job_or_deployment_name: str) -> None:
    """Replay pod logs from a job or deployment to stdout.

    :param namespace: The namspace the
    :param job_or_deployment_name: THe name of the pod or deployment.
    """
    try:
        pod_name = k8s.get_latest_pod_name(namespace, job_or_deployment_name)
        print('-' * 100)
        print(f'---- pod logs for {job_or_deployment_name}')
        print('-' * 100)
        if pod_name is not None:
            pod_logs = k8s.get_pod_logs(namespace, pod_name)
            print(pod_logs)
        else:
            print(f'cannot get logs for {job_or_deployment_name}')
        print('-' * 100)
        print('-' * 100)
    except Exception:
        print(f'cannot get logs for {job_or_deployment_name}')
