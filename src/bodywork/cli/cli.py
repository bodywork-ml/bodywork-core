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
Command Line Interface (CLI)
"""
import sys
import traceback
import urllib3
import warnings
from argparse import ArgumentParser, Namespace
from functools import wraps
from pathlib import Path
from time import sleep
from typing import Callable, Any

import kubernetes
from pkg_resources import get_distribution

from ..config import BodyworkConfig
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
        "--git-repo-url",
        type=str,
        help="Git repository URL containing the Bodywork project.",
    )
    deployment_cmd_parser.add_argument(
        "--git-repo-branch",
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
        "--local-workflow-controller",
        "--local",
        "-L",
        default=False,
        action="store_true",
        help="Run the workflow-controller locally.",
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
        help="Display command only - Deployed Service to search for.",
    )

    deployment_cmd_parser.add_argument(
        "--bodywork-docker-image",
        type=str,
        required=False,
        help="Override the Bodywork Docker image to use - must exist on Bodywork DockerHub repo.",  # noqa
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
        "--git-repo-url",
        type=str,
        help="Git repository URL containing the Bodywork project codebase.",
    )
    cronjob_cmd_parser.add_argument(
        "--git-repo-branch",
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

    # secrets interface
    secret_cmd_parser = cli_arg_subparser.add_parser("secret")
    secret_cmd_parser.set_defaults(func=secret)
    secret_cmd_parser.add_argument(
        "command",
        type=str,
        choices=["create", "delete", "update", "display"],
        help="Secrets action to perform.",
    )
    secret_cmd_parser.add_argument(
        "--group",
        required=False,
        type=str,
        help="The secrets group this secret belongs in.",
    )
    secret_cmd_parser.add_argument(
        "--name", type=str, help="The name given to the Kubernetes secret."
    )
    secret_cmd_parser.add_argument(
        "--data",
        type=str,
        default=[],
        nargs="+",
        help=(
            "Key-values to create in secret - e.g. "
            "--data USERNAME=alex PASSWORD=alex123"
        ),
    )

    # stage interface
    stage_cmd_parser = cli_arg_subparser.add_parser("stage")
    stage_cmd_parser.set_defaults(func=stage)
    stage_cmd_parser.add_argument(
        "git_repo_url", type=str, help="Bodywork project URL."
    )
    stage_cmd_parser.add_argument(
        "git_repo_branch", type=str, help="Bodywork project Git repo branch."
    )
    stage_cmd_parser.add_argument(
        "stage_name", type=str, help="The Bodywork project stage to execute."
    )

    # workflow interface
    workflow_cmd_parser = cli_arg_subparser.add_parser("workflow")
    workflow_cmd_parser.set_defaults(func=workflow)
    workflow_cmd_parser.add_argument(
        "git_repo_url", type=str, help="Bodywork project URL."
    )
    workflow_cmd_parser.add_argument(
        "git_repo_branch", type=str, help="Bodywork project Git repo branch."
    )
    workflow_cmd_parser.add_argument(
        "--bodywork-docker-image",
        type=str,
        help="Bodywork Docker image to use - must exist on Bodywork DockerHub repo.",
    )

    # setup-namespace interface
    setup_namespace_cmd_parser = cli_arg_subparser.add_parser("setup-namespace")
    setup_namespace_cmd_parser.set_defaults(func=setup_namespace)
    setup_namespace_cmd_parser.add_argument(
        "namespace",
        type=str,
        help="Kubernetes namespace to create (if necessary) and setup.",
    )

    # validate interface
    validate_config_file_cmd_parser = cli_arg_subparser.add_parser("validate")
    validate_config_file_cmd_parser.set_defaults(func=validate_config)
    validate_config_file_cmd_parser.add_argument(
        "--file",
        type=str,
        default="bodywork.yaml",
        help="Path to bodywork.yaml config file.",
    )
    validate_config_file_cmd_parser.add_argument(
        "--check-files",
        action="store_true",
        help="Cross-check config with files and directories",
    )

    # Configure Deployment Interface
    configure_cmd_parser = cli_arg_subparser.add_parser("configure-cluster")
    configure_cmd_parser.set_defaults(func=configure_cluster)

    # get config and logger then execute delegated function
    args = cli_arg_parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        cli_arg_parser.exit(
            status=0,
            message=(
                "Deploy machine learning projects developed in Python, to k8s."
                "\n--> see bodywork -h for help"
            ),
        )


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
            print(
                f"Kubernetes API error returned when called from {exception_origin} "
                f"within cli.{func.__name__}: {api_exception_msg(e_value)}"
            )
        except urllib3.exceptions.MaxRetryError:
            e_type, e_value, e_tb = sys.exc_info()
            exception_origin = traceback.extract_tb(e_tb)[2].name
            print(
                f"failed to connect to the Kubernetes API when called from "
                f"{exception_origin} within cli.{func.__name__}: {e_value}"
            )
        except kubernetes.config.ConfigException as e:
            print(
                f"cannot load authentication credentials from kubeconfig file when "
                f"calling cli.{func.__name__}: {e}"
            )

    return wrapper


def debug(args: Namespace) -> None:
    """Debug command handler.

    Runs a blocking sleep process, for use with ad hoc images deployed
    to a kubernetes namespace that can then be logged onto using
    `kubectl exec NAME_OF_POD` for debugging from within the cluster.

    :param args: Arguments passed to the run command from the CLI.
    """
    seconds = args.seconds
    print(f"sleeping for {seconds}s")
    sleep(seconds)
    sys.exit(0)


@handle_k8s_exceptions
def deployment(args: Namespace) -> None:
    """Deploy command handler.

    :param args: Arguments passed to the deploy command from the CLI.
    """
    name = args.name
    namespace = args.namespace
    command = args.command
    retries = args.retries
    git_repo_url = args.git_repo_url
    git_repo_branch = args.git_repo_branch
    run_workflow_controller_locally = args.local_workflow_controller
    service_name = args.service
    image = args.bodywork_docker_image

    if command == "create" and not git_repo_url:
        print("please specify Git repo URL for the deployment you want to create")
        sys.exit(1)
    if (command != "create" and command != "display") and not name:
        print("please specify --name for the deployment")
        sys.exit(1)
    if command == "create":
        if run_workflow_controller_locally:
            pass_through_args = Namespace(
                git_repo_url=git_repo_url,
                git_repo_branch=git_repo_branch,
                bodywork_docker_image=image,
            )
            print("testing with local workflow-controller - retries are inactive")
            workflow(pass_through_args)
        else:
            load_kubernetes_config()
            if not is_namespace_available_for_bodywork(
                BODYWORK_DEPLOYMENT_JOBS_NAMESPACE
            ):
                print(
                    f"namespace={BODYWORK_DEPLOYMENT_JOBS_NAMESPACE} is not setup for"
                    f" use by Bodywork. Have you run 'bodywork configure-cluster' first?"
                )
                sys.exit(1)
            create_workflow_job(
                BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
                name,
                git_repo_url,
                git_repo_branch,
                retries,
                image if image else BODYWORK_DOCKER_IMAGE
            )
    elif command == "delete":
        load_kubernetes_config()
        delete_deployment(name)
    elif command == "logs":
        load_kubernetes_config()
        display_workflow_job_logs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif command == "delete_job":
        load_kubernetes_config()
        delete_workflow_job(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif command == "job_history":
        load_kubernetes_config()
        display_workflow_job_history(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    else:
        load_kubernetes_config()
        display_deployments(namespace, name, service_name)
    sys.exit(0)


@handle_k8s_exceptions
def cronjob(args: Namespace) -> None:
    """Cronjob command handler.

    :param args: Arguments passed to the run command from the CLI.
    """
    command = args.command
    name = args.name
    schedule = args.schedule
    retries = args.retries
    history_limit = args.history_limit
    git_repo_url = args.git_repo_url
    git_repo_branch = args.git_repo_branch
    if (
        command == "create"
        or command == "delete"
        or command == "history"
        or command == "logs"
        or command == "update"
    ) and not name:
        print("please specify --name for the cronjob")
        sys.exit(1)
    elif command == "create" and not schedule:
        print("please specify schedule for the cronjob you want to create")
        sys.exit(1)
    elif command == "create" and not git_repo_url:
        print("please specify Git repo URL for the cronjob you want to create")
        sys.exit(1)
    elif (
        command == "update"
        and (git_repo_url and not git_repo_branch)
        or (not git_repo_url and git_repo_branch)
    ):
        print("Please specify both --git-repo-url and --git-repo-branch.")
        sys.exit(1)

    load_kubernetes_config()
    if command == "create":
        if not is_namespace_available_for_bodywork(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE):
            print(
                f"namespace={BODYWORK_DEPLOYMENT_JOBS_NAMESPACE} is not setup for"
                f" use by Bodywork. Have you run 'bodywork configure-cluster' first?"
            )
            sys.exit(1)
        create_workflow_cronjob(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
            schedule,
            name,
            git_repo_url,
            git_repo_branch if git_repo_branch else "master",
            retries,
            history_limit,
        )
    elif command == "update":
        update_workflow_cronjob(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
            name,
            schedule,
            git_repo_url,
            git_repo_branch,
            retries,
            history_limit,
        )
    elif command == "delete":
        delete_workflow_cronjob(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif command == "history":
        display_workflow_job_history(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    elif command == "logs":
        display_workflow_job_logs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, name)
    else:
        display_cronjobs(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE)
    sys.exit(0)


@handle_k8s_exceptions
def secret(args: Namespace) -> None:
    """Stage command handler.

    :param args: Arguments passed to the run command from the CLI.
    """
    command = args.command
    group = args.group
    name = args.name
    key_value_strings = args.data
    if (command == "create" or command == "delete" or command == "update") and not name:
        print("please specify the name of the secret")
        sys.exit(1)
    if (
        command == "create" or command == "delete" or command == "update"
    ) and not group:
        print("please specify the secret group the secret belongs to")
        sys.exit(1)
    elif (command == "create" or command == "update") and key_value_strings == []:
        print("please specify keys and values for the secret you want to create/update")
        sys.exit(1)
    elif command == "create" or command == "update":
        try:
            var_names_and_values = parse_cli_secrets_strings(key_value_strings)
        except ValueError:
            print(
                "could not parse secret data - example format: "
                "--data USERNAME=alex PASSWORD=alex123"
            )
            sys.exit(1)
        load_kubernetes_config()
        if command == "create":
            create_secret(
                BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name, var_names_and_values
            )
        else:
            update_secret(
                BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name, var_names_and_values
            )
    elif command == "delete":
        load_kubernetes_config()
        delete_secret(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE, group, name)
    elif command == "display" and name and not group:
        print("please specify which secrets group the secret belongs to.")
        sys.exit(1)
    else:
        load_kubernetes_config()
        display_secrets(
            BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
            group,
            name,
        )
    sys.exit(0)


def stage(args: Namespace) -> None:
    """Stage command handler

    :param args: Arguments passed to the run command from the CLI.
    """
    try:
        repo_url = args.git_repo_url
        repo_branch = args.git_repo_branch
        stage_name = args.stage_name
        run_stage(stage_name, repo_url, repo_branch)
        sys.exit(0)
    except Exception:
        sys.exit(1)


@handle_k8s_exceptions
def workflow(args: Namespace) -> None:
    """Workflow execution handler

    :param args: Arguments passed to the workflow command from the CLI.
    """
    try:
        repo_url = args.git_repo_url
        repo_branch = args.git_repo_branch
        docker_image = args.bodywork_docker_image
        load_kubernetes_config()
        run_workflow(repo_url, repo_branch, docker_image_override=docker_image)
        sys.exit(0)
    except BodyworkWorkflowExecutionError:
        sys.exit(1)


@handle_k8s_exceptions
def setup_namespace(args: Namespace) -> None:
    """Setup namespace command handler.

    :param args: Arguments passed to the run command from the CLI.
    """
    namespace = args.namespace
    load_kubernetes_config()
    setup_namespace_with_service_accounts_and_roles(namespace)
    sys.exit(0)


def validate_config(args: Namespace) -> None:
    """Validates a Bodywork config file and returns errors.

    :param args: Arguments passed to the run command from the CLI.
    """
    file_path = Path(args.file)
    check_py_files = args.check_files
    try:
        BodyworkConfig(file_path, check_py_files)
        print(f"--> {file_path} is a valid Bodywork config file.")
        sys.exit(0)
    except (
        FileExistsError,
        BodyworkConfigParsingError,
        BodyworkConfigMissingSectionError,
    ) as e:
        print(f"--> {e}")
        sys.exit(1)
    except BodyworkConfigValidationError as e:
        print(f"- missing or invalid parameters found in {file_path}:")
        missing_or_invalid_param_list = "\n* ".join(e.missing_params)
        print(f"* {missing_or_invalid_param_list}")
        sys.exit(1)


@handle_k8s_exceptions
def configure_cluster(args: Namespace):
    """Configures the cluster with Bodywork namespace and accounts

    :param args: Arguments passed to the run command from the CLI.
    """
    load_kubernetes_config()
    setup_namespace_with_service_accounts_and_roles(BODYWORK_DEPLOYMENT_JOBS_NAMESPACE)
    sys.exit(0)
