from datetime import datetime
from time import sleep
from typing import Optional

from typer import Argument, echo, Exit, Option, Typer

from bodywork.k8s.utils import make_valid_k8s_name

from ..config import BodyworkConfig
from .terminal import print_info, print_warn
from bodywork.cli.workflow_jobs import (
    create_workflow_job,
    create_workflow_cronjob,
    display_cronjobs,
    display_workflow_job_history,
    display_workflow_job_logs,
    delete_workflow_cronjob,
    delete_workflow_job,
    update_workflow_cronjob,
)
from .deployments import display_deployments, delete_deployment
from .secrets import (
    create_secret,
    delete_secret,
    display_secrets,
    parse_cli_secrets_strings,
    update_secret,
)
from .setup_namespace import (
    is_namespace_available_for_bodywork,
    setup_namespace_with_service_accounts_and_roles,
)
from ..exceptions import (
    BodyworkConfigValidationError,
    BodyworkConfigMissingSectionError,
    BodyworkConfigParsingError,
    BodyworkWorkflowExecutionError,
)
from ..constants import BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, BODYWORK_DOCKER_IMAGE
from ..k8s import api_exception_msg, load_kubernetes_config
from ..stage_execution import run_stage
from bodywork.workflow_execution import run_workflow

cli_app = Typer()

create = Typer()
cli_app.add_typer(create, name="create")

get = Typer()
cli_app.add_typer(get, name="get")

update = Typer()
cli_app.add_typer(get, name="update")

delete = Typer()
cli_app.add_typer(delete, name="delete")


try:
    load_kubernetes_config()
except Exception:
    print_warn("Could not authenticate using the active Kubernetes context.")


@cli_app.command("debug")
def _debug(seconds: int = Argument(600)) -> None:
    print_info(f"sleeping for {seconds}s")
    sleep(seconds)
    Exit()


@create.command("deployment")
def _create_deployment(
    git_url: str,
    git_branch: str,
    asynchronous: bool = False,
    image: Optional[str] = None,
    retries: int = 1
):
    if not is_namespace_available_for_bodywork(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE):
        print_warn(
            "Cluster has not been configured for Bodywork - "
            "running 'bodywork configure-cluster'."
        )
        setup_namespace_with_service_accounts_and_roles(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE
        )
    if not asynchronous:
        print_info("Using local workflow controller - retries inactive.")
        try:
            run_workflow(git_url, git_branch, docker_image_override=image)
        except BodyworkWorkflowExecutionError:
            Exit()
    else:
        print_info("Using asynchronous workflow controller.")
        if not is_namespace_available_for_bodywork(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE
        ):
            print_warn(
                f"Namespace = {BODYWORK_DEPLOYMENT_JOBS_NAMESPACE} not setup for "
                f"use by Bodywork - run 'bodywork configure-cluster'"
            )
            Exit()
        async_deployment_job_name = make_valid_k8s_name(
            f"{git_url}.{git_branch}.{datetime.now().isoformat(timespec='seconds')}"
        )
        create_workflow_job(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
            async_deployment_job_name,
            git_url,
            git_branch,
            retries,
            image if image else BODYWORK_DOCKER_IMAGE,
        )
        Exit()


@get.command("deployment")
def _get_deployment(
    name: str,
    service_name: Optional[str] = Argument(None),
    namespace: Optional[str] = None,
    logs: bool = False,
    async_deployment_job_history: bool = False,
):
    if logs and not async_deployment_job_history:
        display_workflow_job_logs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif not logs and async_deployment_job_history:
        display_workflow_job_logs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif logs and async_deployment_job_history:
        print_warn("Cannot specify both --logs and --async-deployment-job-history.")
        Exit(1)
    else:
        display_deployments(namespace, name, service_name)
    Exit()


@update.command("deployment")
def _update_deployment(
    git_url: str,
    git_branch: str,
    asynchronous: bool = False,
    image: Optional[str] = None,
    retries: int = 1
):
    pass


@delete.command("deployment")
def _delete_deployment(name: str, async_deployment_job: bool = False):
    if async_deployment_job:
        delete_workflow_job(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    else:
        delete_deployment(name)
    Exit()


@create.command("cronjob")
def _create_cronjob(
    git_url: str,
    git_branch: str,
    schedule: str = Option(...),
    name: str = Option(...),
    retries: int = 1,
    history_limit: int = 1
):
    if not is_namespace_available_for_bodywork(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE):
        print_warn(
            "Cluster has not been configured for Bodywork - "
            "running 'bodywork configure-cluster'."
        )
        setup_namespace_with_service_accounts_and_roles(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE
        )
    create_workflow_cronjob(
        BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
        schedule,
        make_valid_k8s_name(name),
        git_url,
        git_branch if git_branch else "master",
        retries,
        history_limit,
    )
    Exit()


@get.command("cronjob")
def _get_cronjob(name: str, history: bool = False, logs: str = ""):
    if history and not logs:
        display_workflow_job_history(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif not history and logs:
        display_workflow_job_logs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, logs)
    elif history and logs:
        print_warn("Cannot specify both --logs and --history.")
        Exit(1)
    else:
        display_cronjobs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    Exit()


@update.command("cronjob")
def _update_cronjob(
    git_url: str,
    git_branch: str,
    schedule: str = Option(...),
    name: str = Option(...),
    retries: int = 1,
    history_limit: int = 1
):
    update_workflow_cronjob(
        BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
        name,
        schedule,
        git_url,
        git_branch,
        retries,
        history_limit,
    )
    Exit()


@delete.command("cronjob")
def _delete_cronjob(name: str):
    delete_workflow_cronjob(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    Exit()


if __name__ == "__main__":
    cli_app()
