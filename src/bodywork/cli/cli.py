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
from functools import wraps
from argparse import ArgumentParser, Namespace
from time import sleep
from typing import Callable

import kubernetes
from pkg_resources import get_distribution

from .cronjobs import (
    create_cronjob_in_namespace,
    display_cronjobs_in_namespace,
    display_cronjob_workflow_history,
    display_cronjob_workflow_logs,
    delete_cronjob_in_namespace
)
from .service_deployments import (
    delete_service_deployment_in_namespace,
    display_service_deployments_in_namespace
)
from .secrets import (
    create_secret_in_namespace,
    delete_secret_in_namespace,
    display_secrets_in_namespace,
    parse_cli_secrets_strings
)
from .setup_namespace import (
    is_namespace_available_for_bodywork,
    setup_namespace_with_service_accounts_and_roles
)
from ..exceptions import BodyworkWorkflowExecutionError
from ..k8s import api_exception_msg, load_kubernetes_config
from ..stage import run_stage
from ..workflow import run_workflow


def cli() -> None:
    """Main entry point for the Bodywork CLI.

    Parses commands and arguments and delegates execution to the
    relevant function.
    """
    # top level interface
    cli_arg_parser = ArgumentParser(
        prog='bodywork',
        description='Manage statistical (machine) learning model deployments on k8s.')
    cli_arg_parser.add_argument(
        '--version',
        action='version',
        version=get_distribution('bodywork').version
    )
    cli_arg_subparser = cli_arg_parser.add_subparsers()

    # debug interface
    debug_cmd_parser = cli_arg_subparser.add_parser('debug')
    debug_cmd_parser.set_defaults(func=debug)
    debug_cmd_parser.add_argument(
        'seconds',
        type=int,
        help='Seconds to stay alive before exiting.'
    )

    # cronjob interface
    cronjob_cmd_parser = cli_arg_subparser.add_parser('cronjob')
    cronjob_cmd_parser.set_defaults(func=cronjob)
    cronjob_cmd_parser.add_argument(
        'command',
        type=str,
        choices=['create', 'delete', 'display', 'history', 'logs'],
        help='Timetable action to perform.'
    )
    cronjob_cmd_parser.add_argument(
        '--namespace',
        '--ns',
        required=True,
        type=str,
        help='Kubernetes namespace to operate in.'
    )
    cronjob_cmd_parser.add_argument(
        '--name',
        type=str,
        default='',
        help='The name given to the cronjob or the workflow job.'
    )
    cronjob_cmd_parser.add_argument(
        '--schedule',
        type=str,
        default='',
        help='Workflow cronjob expressed as a cron schedule - e.g. "0,30 * * * *"'
    )
    cronjob_cmd_parser.add_argument(
        '--git-repo-url',
        type=str,
        default='',
        help='Git repository URL containing the Bodywork project codebase'
    )
    cronjob_cmd_parser.add_argument(
        '--git-repo-branch',
        type=str,
        default='master',
        help='Git repository branch to run'
    )
    cronjob_cmd_parser.add_argument(
        '--retries',
        type=int,
        default=2,
        help='Number of times to retry a failed workflow'
    )

    # service interface
    service_cmd_parser = cli_arg_subparser.add_parser('service')
    service_cmd_parser.set_defaults(func=service)
    service_cmd_parser.add_argument(
        'command',
        type=str,
        choices=['delete', 'display'],
        help='Service action to perform.'
    )
    service_cmd_parser.add_argument(
        '--namespace',
        '--ns',
        required=True,
        type=str,
        help='Kubernetes namespace to operate in.'
    )
    service_cmd_parser.add_argument(
        '--name',
        type=str,
        default='',
        help='The name given to the service.'
    )

    # secrets interface
    secret_cmd_parser = cli_arg_subparser.add_parser('secret')
    secret_cmd_parser.set_defaults(func=secret)
    secret_cmd_parser.add_argument(
        'command',
        type=str,
        choices=['create', 'delete', 'display'],
        help='Secrets action to perform.'
    )
    secret_cmd_parser.add_argument(
        '--namespace',
        '--ns',
        required=True,
        type=str,
        help='Kubernetes namespace to operate in.'
    )
    secret_cmd_parser.add_argument(
        '--name',
        type=str,
        default='',
        help='The name given to the Kubernetes secret'
    )
    secret_cmd_parser.add_argument(
        '--data',
        type=str,
        default=[],
        nargs='+',
        help=('Key-values to create in secret - e.g. '
              '--data USERNAME=alex PASSWORD=alex123')
    )

    # stage interface
    stage_cmd_parser = cli_arg_subparser.add_parser('stage')
    stage_cmd_parser.set_defaults(func=stage)
    stage_cmd_parser.add_argument(
        'git_project_repo_url',
        type=str,
        help='Bodywork project URL.'
    )
    stage_cmd_parser.add_argument(
        'git_branch',
        type=str,
        help='Bodywork project Git repo branch.'
    )
    stage_cmd_parser.add_argument(
        'stage_name',
        type=str,
        help='The Bodywork project stage to execute.'
    )

    # workflow interface
    workflow_cmd_parser = cli_arg_subparser.add_parser('workflow')
    workflow_cmd_parser.set_defaults(func=workflow)
    workflow_cmd_parser.add_argument(
        'git_project_repo_url',
        type=str,
        help='Bodywork project URL.'
    )
    workflow_cmd_parser.add_argument(
        'git_branch',
        type=str,
        help='Bodywork project Git repo branch.'
    )
    workflow_cmd_parser.add_argument(
        '--namespace',
        '--ns',
        required=True,
        type=str,
        help='Kubernetes namespace within which to execute the workflow.'
    )
    workflow_cmd_parser.add_argument(
        '--bodywork-docker-image',
        type=str,
        default='',
        help='Bodywork Docker image to use - must exist on Bodywork DockerHub repo.'
    )

    # setup-namespace interface
    setup_namespace_cmd_parser = cli_arg_subparser.add_parser('setup-namespace')
    setup_namespace_cmd_parser.set_defaults(func=setup_namespace)
    setup_namespace_cmd_parser.add_argument(
        'namespace',
        type=str,
        help='Kubernetes namespace to create (if necessary) and setup.'
    )

    # get config and logger then execute delegated function
    args = cli_arg_parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        cli_arg_parser.exit(
            status=0,
            message=('Manage statistical (machine) learning model deployments on k8s.'
                     '\n--> see bodywork -h for help')
        )


def handle_k8s_exceptions(func: Callable[..., None]) -> Callable[..., None]:
    """Decorator for handling k8s API exceptions on the CLI.

    :param func: The inner function to wrap with k8s exception handling.
    :return: The original function wrapped by a function that handles
        k8s API exceptions.
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> None:
        try:
            func(*args, **kwargs)
        except kubernetes.client.rest.ApiException:
            e_type, e_value, e_tb = sys.exc_info()
            exception_origin = traceback.extract_tb(e_tb)[2].name
            print(f'Kubernetes API error returned when called from {exception_origin} '
                  f'within cli.{func.__name__}: {api_exception_msg(e_value)}')
        except urllib3.exceptions.MaxRetryError:
            e_type, e_value, e_tb = sys.exc_info()
            exception_origin = traceback.extract_tb(e_tb)[2].name
            print(f'failed to connect to the Kubernetes API when called from '
                  f'{exception_origin} within cli.{func.__name__}: {e_value}')
        except kubernetes.config.ConfigException as e:
            print(f'cannot load authenticaion credentials from kubeconfig file when '
                  f'calling cli.{func.__name__}: {e}')
    return wrapper


def debug(args: Namespace) -> None:
    """Debug command handler.

    Runs a blocking sleep process, for use with ad hoc images deployed
    to a kubernetes namespace that can then be logged onto using
    `kubectl exec NAME_OF_POD` for debugging from withint he a cluster.

    :param args: Arguments passed to the run command from the CLI.
    :param logger: Bodywork logger.
    """
    seconds = args.seconds
    print(f'sleeping for {seconds}s')
    sleep(seconds)
    sys.exit(0)


@handle_k8s_exceptions
def cronjob(args: Namespace) -> None:
    """Timetable command handler.

    :param args: Arguments passed to the run command from the CLI.
    :param logger: Bodywork logger.
    """
    command = args.command
    namespace = args.namespace
    name = args.name
    schedule = args.schedule
    retries = args.retries
    git_repo_url = args.git_repo_url
    git_repo_branch = args.git_repo_branch
    if ((command == 'create' or command == 'delete' or command == 'history'
            or command == 'logs') and name == ''):
        print('please specify --name for the cronjob')
        sys.exit(1)
    elif command == 'create' and schedule == '':
        print('please specify schedule for the cronjob you want to create')
        sys.exit(1)
    elif command == 'create' and git_repo_url == '':
        print('please specify Git repo URL for the cronjob you want to create')
        sys.exit(1)
    elif command == 'create':
        load_kubernetes_config()
        if not is_namespace_available_for_bodywork(namespace):
            print(f'namespace={namespace} is not setup for use by Bodywork')
            sys.exit(1)
        create_cronjob_in_namespace(
            namespace,
            schedule,
            name,
            git_repo_url,
            git_repo_branch,
            retries
        )
    elif command == 'delete':
        load_kubernetes_config()
        delete_cronjob_in_namespace(namespace, name)
    elif command == 'history':
        load_kubernetes_config()
        display_cronjob_workflow_history(namespace, name)
    elif command == 'logs':
        load_kubernetes_config()
        display_cronjob_workflow_logs(namespace, name)
    else:
        load_kubernetes_config()
        display_cronjobs_in_namespace(namespace)
    sys.exit(0)


@handle_k8s_exceptions
def service(args: Namespace) -> None:
    """Service deployment command handler.

    :param args: Arguments passed to the run command from the CLI.
    :param logger: Bodywork logger.
    """
    command = args.command
    namespace = args.namespace
    name = args.name
    if command == 'delete' and name == '':
        print('please specify --name for the service')
        sys.exit(1)
    elif command == 'delete':
        load_kubernetes_config()
        delete_service_deployment_in_namespace(namespace, name)
    else:
        load_kubernetes_config()
        display_service_deployments_in_namespace(namespace)
    sys.exit(0)


@handle_k8s_exceptions
def secret(args: Namespace) -> None:
    """Stage command handler.

    :param args: Arguments passed to the run command from the CLI.
    :param logger: Bodywork logger.
    """
    command = args.command
    namespace = args.namespace
    name = args.name
    key_value_strings = args.data
    if (command == 'create' or command == 'delete') and name == '':
        print('please specify a name for the secret you want to create')
        sys.exit(1)
    elif command == 'create' and key_value_strings == []:
        print('please specify keys and values for the secret you want to create')
        sys.exit(1)
    elif command == 'create':
        try:
            var_names_and_values = parse_cli_secrets_strings(key_value_strings)
        except ValueError:
            print('could not parse secret data - example format: '
                  '--data USERNAME=alex PASSWORD=alex123')
            sys.exit(1)
        load_kubernetes_config()
        create_secret_in_namespace(namespace, name, var_names_and_values)
    elif command == 'delete':
        load_kubernetes_config()
        delete_secret_in_namespace(namespace, name)
    else:
        load_kubernetes_config()
        display_secrets_in_namespace(namespace, name if name != '' else None)
    sys.exit(0)


def stage(args: Namespace) -> None:
    """Stage command handler

    :param args: Arguments passed to the run command from the CLI.
    :param logger: Bodywork logger.
    """
    try:
        repo_url = args.git_project_repo_url
        repo_branch = args.git_branch
        stage_name = args.stage_name
        run_stage(stage_name, repo_url, repo_branch)
        sys.exit(0)
    except Exception:
        sys.exit(1)


@handle_k8s_exceptions
def workflow(args: Namespace) -> None:
    """Workflow execution handler

    :param args: Arguments passed to the workflow command from the CLI.
    :param logger: Bodywork logger.
    """
    try:
        namespace = args.namespace
        repo_url = args.git_project_repo_url
        repo_branch = args.git_branch
        docker_image = args.bodywork_docker_image
        load_kubernetes_config()
        if not is_namespace_available_for_bodywork(namespace):
            print(f'namespace={namespace} is not setup for use by Bodywork')
            sys.exit(1)
        run_workflow(
            namespace,
            repo_url,
            repo_branch,
            docker_image_override=(None if docker_image == '' else docker_image)
        )
        sys.exit(0)
    except BodyworkWorkflowExecutionError:
        sys.exit(1)


@handle_k8s_exceptions
def setup_namespace(args: Namespace) -> None:
    """Setup namespace command handler.

    :param args: Arguments passed to the run command from the CLI.
    :param logger: Bodywork logger.
    """
    namespace = args.namespace
    load_kubernetes_config()
    setup_namespace_with_service_accounts_and_roles(namespace)
    sys.exit(0)
