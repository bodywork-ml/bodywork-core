import sys
import traceback
import urllib3
import warnings
from datetime import datetime
from functools import wraps
from pathlib import Path
from time import sleep
from typing import Any, Callable, List, Optional

import kubernetes
from pkg_resources import get_distribution
from typer import Argument, Option, Typer

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

warnings.simplefilter(action="ignore")

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
except Exception as e:
    print_warn(f"Could not authenticate using the active Kubernetes context. \n--> {e}")


def handle_k8s_exceptions(func: Callable[..., None]) -> Callable[..., None]:
    """Decorator for handling k8s API exceptions on the CLI.

    :param func: The inner function to wrap with k8s exception handling.
    :return: The original function wrapped by a function that handles
        k8s API exceptions.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            func(*args, **kwargs)
        except kubernetes.client.rest.ApiException:
            e_type, e_value, e_tb = sys.exc_info()
            exception_origin = traceback.extract_tb(e_tb)[2].name
            print_warn(
                f"Kubernetes API error returned when called from {exception_origin} "
                f"within cli.{func.__name__}: {api_exception_msg(e_value)}"
            )
        except urllib3.exceptions.MaxRetryError:
            e_type, e_value, e_tb = sys.exc_info()
            exception_origin = traceback.extract_tb(e_tb)[2].name
            print_warn(
                f"Failed to connect to the Kubernetes API when called from "
                f"{exception_origin} within cli.{func.__name__}: {e_value}"
            )
        except kubernetes.config.ConfigException as e:
            print_warn(
                f"Cannot load authentication credentials from kubeconfig file when "
                f"calling cli.{func.__name__}: {e}"
            )
    return wrapper


@cli_app.command("validate")
def _validate_config(file: str = "bodywork.yaml", check_files: bool = False):
    file_path = Path(file)
    try:
        BodyworkConfig(file_path, check_files)
        print_info(f"--> {file_path} is a valid Bodywork config file.")
        sys.exit(0)
    except (
        FileExistsError,
        BodyworkConfigParsingError,
        BodyworkConfigMissingSectionError,
    ) as e:
        print_warn(f"--> {e}")
        sys.exit(1)
    except BodyworkConfigValidationError as e:
        print_warn(f"Missing or invalid parameters found in {file_path}:")
        missing_or_invalid_param_list = "\n* ".join(e.missing_params)
        print_warn(f"* {missing_or_invalid_param_list}")
        sys.exit(1)


@cli_app.command("version")
def _version():
    print_info(get_distribution("bodywork").version)
    sys.exit(0)


@cli_app.command("configure-cluster")
@handle_k8s_exceptions
def _configure_cluster():
    setup_namespace_with_service_accounts_and_roles(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE)
    sys.exit(0)


@cli_app.command("stage", hidden=True)
@handle_k8s_exceptions
def _stage(git_url: str, git_branch: str, stage_name: str):
    try:
        run_stage(stage_name, git_url, git_branch)
        sys.exit(0)
    except Exception:
        sys.exit(1)


@cli_app.command("debug", hidden=True)
@handle_k8s_exceptions
def _debug(seconds: int = Argument(600)) -> None:
    print_info(f"sleeping for {seconds}s")
    sleep(seconds)
    sys.exit(0)


@create.command("deployment")
@handle_k8s_exceptions
def _create_deployment(
    git_url: str,
    git_branch: str,
    asynchronous: bool = Option(False, "--async"),
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
            sys.exit(0)
    else:
        print_info("Using asynchronous workflow controller.")
        print_warn(
            "Cluster has not been configured for Bodywork - "
            "running 'bodywork configure-cluster'."
        )
        setup_namespace_with_service_accounts_and_roles(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE
        )
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
        sys.exit(0)


@get.command("deployment")
@get.command("deployments")
@handle_k8s_exceptions
def _get_deployment(
    name: str = Argument(None),
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
        sys.exit(1)
    else:
        display_deployments(namespace, name, service_name)
    sys.exit(0)


@update.command("deployment")
@handle_k8s_exceptions
def _update_deployment(
    git_url: str,
    git_branch: str,
    asynchronous: bool = Option(False, "--async"),
    image: Optional[str] = None,
    retries: int = 1
):
    pass


@delete.command("deployment")
@handle_k8s_exceptions
def _delete_deployment(name: str, async_deployment_job: bool = False):
    if async_deployment_job:
        delete_workflow_job(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    else:
        delete_deployment(name)
    sys.exit(0)


@create.command("cronjob")
@handle_k8s_exceptions
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
    sys.exit(0)


@get.command("cronjob")
@get.command("cronjobs")
@handle_k8s_exceptions
def _get_cronjob(name: str, history: bool = False, logs: str = ""):
    if history and not logs:
        display_workflow_job_history(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif not history and logs:
        display_workflow_job_logs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, logs)
    elif history and logs:
        print_warn("Cannot specify both --logs and --history.")
        sys.exit(1)
    else:
        display_cronjobs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    sys.exit(0)


@update.command("cronjob")
@handle_k8s_exceptions
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
    sys.exit(0)


@delete.command("cronjob")
@handle_k8s_exceptions
def _delete_cronjob(name: str):
    delete_workflow_cronjob(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    sys.exit(0)


@create.command("secret")
@handle_k8s_exceptions
def _create_secret(name: str, data: List[str] = Option(...), group: str = Option(...)):
    try:
        var_names_and_values = parse_cli_secrets_strings(data)
    except ValueError:
        print_warn(
            "Could not parse secret data - example format: --data USERNAME=alex "
            "PASSWORD=alex123"
        )
        sys.exit(1)
    create_secret(
        BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name, var_names_and_values
    )
    sys.exit(0)


@get.command("secret")
@get.command("secrets")
@handle_k8s_exceptions
def _get_secret(
    name: str = Argument(None), group: str = Option(None)
):
    if name and not group:
        print_warn("Please specify which secrets group the secret belongs to.")
        sys.exit(1)
    display_secrets(
        BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
        group,
        name,
    )
    sys.exit(0)


@update.command("secret")
@handle_k8s_exceptions
def _update_secret(name: str, data: List[str] = Option(...), group: str = Option(...)):
    try:
        var_names_and_values = parse_cli_secrets_strings(data)
    except ValueError:
        print_warn(
            "Could not parse secret data - example format: --data USERNAME=alex "
            "PASSWORD=alex123"
        )
        sys.exit(1)
    update_secret(
        BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name, var_names_and_values
    )
    sys.exit(0)


@delete.command("secret")
@handle_k8s_exceptions
def _delete_secret(name: str, group: str = Option(...)):
    delete_secret(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name)
