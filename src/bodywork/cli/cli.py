import sys
import traceback
import urllib3
import warnings
from datetime import datetime
from functools import wraps
from pathlib import Path
from time import sleep
from typing import Callable, Any
from .terminal import console

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

def cli() -> None:
    """Main entry point for the Bodywork CLI.

    Parses commands and arguments and delegates execution to the
    relevant function.
    """
    # top level interface
    cli_arg_parser = ArgumentParser(
        prog="bodywork",
        description="Deploy machine learning projects developed in Python, to k8s.",
    )
    cli_arg_parser.add_argument(
        "--version", action="version", version=get_distribution("bodywork").version
    )
    cli_arg_subparser = cli_arg_parser.add_subparsers()

    # debug interface
    debug_cmd_parser = cli_arg_subparser.add_parser("debug")
    debug_cmd_parser.set_defaults(func=debug)
    debug_cmd_parser.add_argument(
        "seconds", type=int, help="Seconds to stay alive before exiting."
    )

    # deployment interface
    deployment_cmd_parser = cli_arg_subparser.add_parser("deployment")
    deployment_cmd_parser.set_defaults(func=deployment)
    deployment_cmd_parser.add_argument(
        "command",
        type=str,
        choices=["create", "delete", "display", "logs", "delete_job", "display_job"],
        help="Deployment action to perform.",
    )
    deployment_cmd_parser.add_argument(
        "--name", type=str, help="The name given to the workflow job."
    )
    deployment_cmd_parser.add_argument(
        "--git-url",
        type=str,
        help="Git repository URL containing the Bodywork project.",
    )
    deployment_cmd_parser.add_argument(
        "--git-branch",
        type=str,
        default="master",
        help="Git repository branch to run.",
    )
    deployment_cmd_parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Number of times to retry a failed workflow job.",
    )
    deployment_cmd_parser.add_argument(
        "--async",
        "--A",
        dest="async_workflow",
        default=False,
        action="store_true",
        help="Run workflow-controller asynchronously (remotely on the k8s cluster).",
    )
    deployment_cmd_parser.add_argument(
        "--namespace",
        "--ns",
        required=False,
        type=str,
        help="Display command only - K8s namespace to look in.",
    )
    deployment_cmd_parser.add_argument(
        "--service",
        "--s",
        required=False,
        type=str,
        help="Display command only - deployed Service to search for.",
    )
    deployment_cmd_parser.add_argument(
        "--bodywork-docker-image",
        type=str,
        required=False,
        help="Override the Bodywork Docker image to use - must exist on Bodywork DockerHub repo.",  # noqa
    )
    deployment_cmd_parser.add_argument(
        "--ssh",
        dest="ssh_key_path",
        type=str,
        required=False,
        help="The filepath to the ssh key to use (typically located in your .ssh folder).",  # noqa
    )
    deployment_cmd_parser.add_argument(
        "--group",
        type=str,
        required=False,
        help="For async workflows, the secrets group to create the SSH key in (must match secrets group in config).",  # noqa
    )
    # cronjob interface
    cronjob_cmd_parser = cli_arg_subparser.add_parser("cronjob")
    cronjob_cmd_parser.set_defaults(func=cronjob)
    cronjob_cmd_parser.add_argument(
        "command",
        type=str,
        choices=["create", "update", "delete", "display", "history", "logs"],
        help="Cronjob action to perform.",
    )
    cronjob_cmd_parser.add_argument(
        "--name", type=str, help="The name given to the cronjob."
    )
    cronjob_cmd_parser.add_argument(
        "--schedule",
        type=str,
        help='Workflow cronjob expressed as a cron schedule - e.g. "0 30 * * *".',
    )
    cronjob_cmd_parser.add_argument(
        "--git-url",
        type=str,
        help="Git repository URL containing the Bodywork project codebase.",
    )
    cronjob_cmd_parser.add_argument(
        "--git-branch",
        type=str,
        help="Git repository branch to run.",
    )
    cronjob_cmd_parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Number of times to retry a failed workflow job.",
    )
    cronjob_cmd_parser.add_argument(
        "--history-limit",
        type=int,
        default=1,
        help="Minimum number of historic workflow jobs to keep for logs.",
    )
    cronjob_cmd_parser.add_argument(
        "--ssh",
        dest="ssh_key_path",
        type=str,
        required=False,
        help="The filepath to the ssh key to use (typically located in your .ssh folder).",  # noqa
    )
    cronjob_cmd_parser.add_argument(
        "--group",
        type=str,
        required=False,
        help="For async workflows, the secrets group to create the SSH key in (must match secrets group in config).",  # noqa
    )

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
@k8s_auth
def _configure_cluster():
    setup_namespace_with_service_accounts_and_roles(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE)
    sys.exit(0)

    :param args: Arguments passed to the deploy command from the CLI.
    """
    name = args.name
    namespace = args.namespace
    command = args.command
    retries = args.retries
    git_url = args.git_url
    git_branch = args.git_branch
    async_workflow = args.async_workflow
    service_name = args.service
    image = args.bodywork_docker_image
    ssh_key_path = args.ssh_key_path
    group = args.group

    if command == "create" and not git_url:
        print_warn("Please specify Git repo URL for the deployment you want to create.")
        sys.exit(1)
    if (command != "create" and command != "display") and not name:
        print_warn("Please specify --name for the deployment job.")
        sys.exit(1)
    if command == "create":
        load_kubernetes_config()
        if not is_namespace_available_for_bodywork(BODYWORK_NAMESPACE):
            print_warn(
                "Cluster has not been configured for Bodywork - "
                "running 'bodywork configure-cluster'."
            )
            setup_namespace_with_service_accounts_and_roles(BODYWORK_NAMESPACE)
        if not async_workflow:
            print_info("Using local workflow controller - retries inactive.")
            try:
                console.rule(
                    f"[green]deploying[/green] [bold purple]{git_branch}[/bold purple] "
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
                        docker_image_override=image,
                        ssh_key_path=ssh_key_path,
                    )
                console.rule(characters="=", style="green")
            except BodyworkWorkflowExecutionError:
                sys.exit(1)
        else:
            print_info("Using asynchronous workflow controller.")
            create_workflow_job(
                BODYWORK_NAMESPACE,
                name,
                git_url,
                git_branch,
                retries,
                image if image else BODYWORK_DOCKER_IMAGE,
                ssh_key_path,
                group,
            )
    elif command == "delete":
        load_kubernetes_config()
        delete_deployment(name)
    elif command == "logs":
        load_kubernetes_config()
        display_workflow_job_logs(BODYWORK_NAMESPACE, name)
    elif command == "delete_job":
        load_kubernetes_config()
        delete_workflow_job(BODYWORK_NAMESPACE, name)
    elif command == "job_history":
        load_kubernetes_config()
        display_workflow_job_history(BODYWORK_NAMESPACE, name)
    else:
        load_kubernetes_config()
        display_deployments(namespace, name, service_name)
    sys.exit(0)


@cli_app.command("debug", hidden=True)
def _debug(seconds: int = Argument(600)) -> None:
    print_info(f"sleeping for {seconds}s")
    sleep(seconds)
    sys.exit(0)

    :param args: Arguments passed to the run command from the CLI.
    """
    command = args.command
    name = args.name
    schedule = args.schedule
    retries = args.retries
    history_limit = args.history_limit
    git_url = args.git_url
    git_branch = args.git_branch
    ssh_key_path = args.ssh_key_path
    group = args.group
    if (
        command == "create"
        or command == "delete"
        or command == "history"
        or command == "logs"
        or command == "update"
    ) and not name:
        print_warn("Please specify --name for the cronjob.")
        sys.exit(1)
    elif command == "create" and not schedule:
        print_warn("Please specify schedule for the cronjob you want to create.")
        sys.exit(1)
    elif command == "create" and not git_url:
        print_warn("Please specify Git repo URL for the cronjob you want to create.")
        sys.exit(1)
    elif (
        command == "update"
        and (git_url and not git_branch)
        or (not git_url and git_branch)
    ):
        print("Please specify both --git-url and --git-branch.")
        sys.exit(1)

    load_kubernetes_config()
    if command == "create":
        if not is_namespace_available_for_bodywork(BODYWORK_NAMESPACE):
            print_warn(
                f"Namespace = {BODYWORK_NAMESPACE} not setup for "
                f"use by Bodywork - run 'bodywork configure-cluster'"
            )
            sys.exit(1)
        create_workflow_cronjob(
            BODYWORK_NAMESPACE,
            schedule,
            name,
            git_url,
            git_branch if git_branch else "master",
            retries,
            history_limit,
            ssh_key_path,
            group,
        )
    elif command == "update":
        update_workflow_cronjob(
            BODYWORK_NAMESPACE,
            name,
            schedule,
            git_url,
            git_branch,
            retries,
            image if image else BODYWORK_DOCKER_IMAGE,
        )
    elif command == "delete":
        delete_workflow_cronjob(BODYWORK_NAMESPACE, name)
    elif command == "history":
        display_workflow_job_history(BODYWORK_NAMESPACE, name)
    elif command == "logs":
        display_workflow_job_logs(BODYWORK_NAMESPACE, name)
    else:
        display_cronjobs(BODYWORK_NAMESPACE, name)
    sys.exit(0)


@update.command("cronjob")
@handle_k8s_exceptions
@k8s_auth
def _update_cronjob(
    git_url: str = Argument(...),
    git_branch: str = Argument(...),
    schedule: str = Option(...),
    name: str = Option(...),
    retries: int = Option(1),
    history_limit: int = Option(1),
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
@k8s_auth
def _delete_cronjob(name: str = Argument(...)):
    delete_workflow_cronjob(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    sys.exit(0)


@create.command("secret")
@handle_k8s_exceptions
@k8s_auth
def _create_secret(
    name: str = Argument(...), group: str = Option(...), data: List[str] = Option(...)
):
    try:
        var_names_and_values = parse_cli_secrets_strings(data)
        create_secret(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name, var_names_and_values
        )
    except ValueError:
        print_warn(
            "Could not parse secret data - example format: --data USERNAME=alex "
            "PASSWORD=alex123"
        )
        sys.exit(1)
    elif command == "create" or command == "update":
        try:
            var_names_and_values = parse_cli_secrets_strings(key_value_strings)
        except ValueError:
            print_warn(
                "Could not parse secret data - example format: --data USERNAME=alex "
                "PASSWORD=alex123"
            )
            sys.exit(1)
        load_kubernetes_config()
        if command == "create":
            create_secret(BODYWORK_NAMESPACE, group, name, var_names_and_values)
        else:
            update_secret(BODYWORK_NAMESPACE, group, name, var_names_and_values)
    elif command == "delete":
        load_kubernetes_config()
        delete_secret(BODYWORK_NAMESPACE, group, name)
    elif command == "display" and name and not group:
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
        update_secret(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name, var_names_and_values
        )
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


@delete.command("secret")
@handle_k8s_exceptions
def configure_cluster(args: Namespace):
    """Configures the cluster with Bodywork namespace and accounts

    :param args: Arguments passed to the run command from the CLI.
    """
    load_kubernetes_config()
    setup_namespace_with_service_accounts_and_roles(BODYWORK_NAMESPACE)
    sys.exit(0)
