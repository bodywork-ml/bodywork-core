import sys
import traceback
import urllib3
import warnings
from datetime import datetime
from functools import wraps
from pathlib import Path
from time import sleep
from typing import Any, Callable, List

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
    delete_secret_group,
)
from .setup_namespace import (
    is_namespace_available_for_bodywork,
    setup_namespace_with_service_accounts_and_roles,
)
from .terminal import console
from ..exceptions import (
    BodyworkConfigFileExistsError,
    BodyworkConfigValidationError,
    BodyworkConfigMissingSectionError,
    BodyworkConfigParsingError,
    BodyworkWorkflowExecutionError,
)
from ..constants import BODYWORK_NAMESPACE, BODYWORK_DOCKER_IMAGE
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
cli_app.add_typer(update, name="update")

delete = Typer()
cli_app.add_typer(delete, name="delete")


def k8s_auth(func: Callable[..., None]) -> Callable[..., None]:
    """Decorator for handling k8s authentication for CLI commands.

    :param func: The inner function to wrap with k8s exception handling.
    :return: The original function wrapped by a function that handles
        k8s API exceptions.
    """
    try:
        load_kubernetes_config()
    except Exception as e:
        print_warn(f"Could not authenticate with active Kubernetes context. \n--> {e}")
    return func


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
def _validate_config(
    file: str = Option("bodywork.yaml"), check_files: bool = Option(False)
):
    file_path = Path(file)
    try:
        BodyworkConfig(file_path, check_files)
        print_info(f"--> {file_path} is a valid Bodywork config file.")
        sys.exit(0)
    except (
        BodyworkConfigFileExistsError,
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
@k8s_auth
def _configure_cluster():
    setup_namespace_with_service_accounts_and_roles(BODYWORK_NAMESPACE)
    sys.exit(0)


@cli_app.command("stage", hidden=True)
def _stage(
    git_url: str = Argument(...),
    git_branch: str = Option("", "--branch"),
    stage_name: str = Argument(...),
):
    try:
        run_stage(stage_name, git_url, git_branch)
        sys.exit(0)
    except Exception:
        sys.exit(1)


@cli_app.command("debug", hidden=True)
def _debug(seconds: int = Argument(600)) -> None:
    print_info(f"sleeping for {seconds}s")
    sleep(seconds)
    sys.exit(0)


@create.command("deployment")
@handle_k8s_exceptions
@k8s_auth
def _create_deployment(
    git_url: str = Argument(...),
    git_branch: str = Option("", "--branch"),
    asynchronous: bool = Option(False, "--async", hidden=True),
    asynchronous_job_name: str = Option("", "--async-job-name", hidden=True),
    ssh_key_path: str = Option("", "--ssh"),
    secrets_group: str = Option("", "--group", "--secrets-group"),
    image: str = Option(None, "--bodywork-image", hidden=True),
    retries: int = Option(1),
):
    if not is_namespace_available_for_bodywork(BODYWORK_NAMESPACE):
        print_warn(
            "Cluster has not been configured for Bodywork - "
            "running 'bodywork configure-cluster'."
        )
        setup_namespace_with_service_accounts_and_roles(BODYWORK_NAMESPACE)
    if not asynchronous:
        print_info("Using local workflow controller - retries inactive.")
        try:
            git_branch_ = "default" if not git_branch else git_branch
            console.rule(
                f"[green]deploying[/green] [bold purple]{git_branch_}[/bold purple] "
                f"[green]branch from[/green] [bold purple]{git_url}[/bold purple]",
                characters="=",
                style="green",
            )
            with console.status(
                "[purple]Bodywork deploying[/purple]", spinner="aesthetic"
            ):
                run_workflow(
                    git_url,
                    git_branch,
                    ssh_key_path=ssh_key_path,
                    docker_image_override=image,
                )
            console.rule(characters="=", style="green")
        except BodyworkWorkflowExecutionError:
            sys.exit(1)
    else:
        if not asynchronous_job_name:
            async_deployment_job_name = make_valid_k8s_name(
                f"async-workflow-{git_url}.{git_branch}."
                f"{datetime.now().isoformat(timespec='seconds')}"
            )
        else:
            async_deployment_job_name = f"async-workflow-{asynchronous_job_name}"
        print_info("Using asynchronous workflow controller.")
        create_workflow_job(
            BODYWORK_NAMESPACE,
            async_deployment_job_name,
            git_url,
            git_branch,
            retries,
            image if image else BODYWORK_DOCKER_IMAGE,
            ssh_key_path,
            secrets_group,
        )
        sys.exit(0)


@get.command("deployment")
@get.command("deployments")
@handle_k8s_exceptions
@k8s_auth
def _get_deployment(
    name: str = Argument(None),
    service_name: str = Argument(None),
    asynchronous: bool = Option(False, "--async", hidden=True),
    logs: str = Option(""),
    namespace: str = Option(None),
):
    if asynchronous:
        if logs:
            display_workflow_job_logs(BODYWORK_NAMESPACE, logs)
        else:
            display_workflow_job_history(BODYWORK_NAMESPACE, "async-workflow")
    else:
        display_deployments(namespace, name, service_name)
    sys.exit(0)


@update.command("deployment")
@handle_k8s_exceptions
@k8s_auth
def _update_deployment(
    git_url: str = Argument(...),
    git_branch: str = Option("", "--branch"),
    asynchronous: bool = Option(False, "--async", hidden=True),
    asynchronous_job_name: str = Option("", "--async-job-name", hidden=True),
    image: str = Option(None, "--bodywork-image", hidden=True),
    retries: int = Option(1),
):
    _create_deployment(
        git_url=git_url,
        git_branch=git_branch,
        asynchronous=asynchronous,
        asynchronous_job_name=asynchronous_job_name,
        ssh_key_path="",
        secrets_group="",
        image=image,
        retries=retries,
    )


@delete.command("deployment")
@handle_k8s_exceptions
@k8s_auth
def _delete_deployment(
    name: str = Argument(...), asynchronous: bool = Option(False, "--async", hidden=True)
):
    if asynchronous:
        delete_workflow_job(BODYWORK_NAMESPACE, name)
    else:
        delete_deployment(name)
    sys.exit(0)


@create.command("cronjob")
@handle_k8s_exceptions
@k8s_auth
def _create_cronjob(
    git_url: str = Argument(...),
    git_branch: str = Option("", "--branch"),
    schedule: str = Option(...),
    name: str = Option(...),
    retries: int = Option(1),
    history_limit: int = Option(1),
    ssh_key_path: str = Option("", "--ssh"),
    secrets_group: str = Option("", "--group", "--secrets-group"),
):
    create_workflow_cronjob(
        BODYWORK_NAMESPACE,
        schedule,
        make_valid_k8s_name(name),
        git_url,
        git_branch if git_branch else "master",
        retries,
        history_limit,
        ssh_key_path,
        secrets_group,
    )
    sys.exit(0)


@get.command("cronjob")
@get.command("cronjobs")
@handle_k8s_exceptions
@k8s_auth
def _get_cronjob(
    name: str = Argument(None),
    history: bool = Option(False),
    logs: str = Option(""),
):
    if name and history and not logs:
        display_workflow_job_history(BODYWORK_NAMESPACE, name)
    elif name and not history and logs:
        display_workflow_job_logs(BODYWORK_NAMESPACE, logs)
    elif name and history and logs:
        print_warn("Cannot specify both --logs and --history.")
        sys.exit(1)
    else:
        display_cronjobs(BODYWORK_NAMESPACE, name)
    sys.exit(0)


@update.command("cronjob")
@handle_k8s_exceptions
@k8s_auth
def _update_cronjob(
    git_url: str = Argument(...),
    git_branch: str = Option("", "--branch"),
    schedule: str = Option(...),
    name: str = Option(...),
    retries: int = Option(1),
    history_limit: int = Option(1),
):
    update_workflow_cronjob(
        BODYWORK_NAMESPACE,
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
@k8s_auth
def _delete_cronjob(name: str = Argument(...)):
    delete_workflow_cronjob(BODYWORK_NAMESPACE, name)
    sys.exit(0)


@create.command("secret")
@handle_k8s_exceptions
@k8s_auth
def _create_secret(
    name: str = Argument(...), group: str = Option(...), data: List[str] = Option(...)
):
    try:
        var_names_and_values = parse_cli_secrets_strings(data)
        create_secret(BODYWORK_NAMESPACE, group, name, var_names_and_values)
    except ValueError:
        print_warn(
            "Could not parse secret data - example format: --data USERNAME=alex "
            "PASSWORD=alex123"
        )
        sys.exit(1)
    sys.exit(0)


@get.command("secret")
@get.command("secrets")
@handle_k8s_exceptions
@k8s_auth
def _get_secret(
    name: str = Argument(None), group: str = Option(None)
):
    if name and not group:
        print_warn("Please specify which secrets group the secret belongs to.")
        sys.exit(1)
    else:
        display_secrets(
            BODYWORK_NAMESPACE,
            group,
            name,
        )
        sys.exit(0)


@update.command("secret")
@handle_k8s_exceptions
@k8s_auth
def _update_secret(
    name: str = Argument(...), group: str = Option(...), data: List[str] = Option(...)
):
    try:
        var_names_and_values = parse_cli_secrets_strings(data)
        update_secret(BODYWORK_NAMESPACE, group, name, var_names_and_values)
        sys.exit(0)
    except ValueError:
        print_warn(
            "Could not parse secret data - example format: --data USERNAME=alex "
            "PASSWORD=alex123"
        )
        sys.exit(1)


@delete.command("secret")
@handle_k8s_exceptions
@k8s_auth
def _delete_secret(
    name: str = Argument(None), group: str = Option(None)
):
    if name:
        if not group:
            print_warn("Please specify which secrets group the secret belongs to.")
            sys.exit(1)
        else:
            delete_secret(BODYWORK_NAMESPACE, group, name)
            sys.exit(0)
    elif group:
        delete_secret_group(BODYWORK_NAMESPACE, group)
        sys.exit(0)
    else:
        print_warn("Please specify a secret or a secrets group to delete.")
        sys.exit(1)
