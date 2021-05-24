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
Kubernetes API sub-module.

This collection of functions utilise the low-level Kubernetes Python
client to perform Bodywork-specific tasks.
"""
from .auth import (
    cluster_role_binding_exists,
    cluster_role_exists,
    delete_cluster_role_binding,
    workflow_cluster_role_binding_name,
    load_kubernetes_config,
    service_account_exists,
    setup_job_and_deployment_service_accounts,
    setup_workflow_service_account,
)
from .workflow_jobs import (
    configure_workflow_job,
    configure_workflow_cronjob,
    create_workflow_job,
    create_workflow_cronjob,
    delete_workflow_cronjob,
    list_workflow_cronjobs,
    list_workflow_jobs,
)
from .batch_jobs import (
    JobStatus,
    configure_batch_stage_job,
    create_job,
    delete_job,
    monitor_jobs_to_completion,
)
from .namespaces import namespace_exists, create_namespace, delete_namespace
from .pod_logs import get_latest_pod_name, get_pod_logs
from .secrets import (
    configure_env_vars_from_secrets,
    secret_exists,
    create_secret,
    delete_secret,
    list_secrets_in_namespace,
)
from .service_deployments import (
    DeploymentStatus,
    configure_service_stage_deployment,
    create_deployment,
    is_existing_deployment,
    update_deployment,
    rollback_deployment,
    delete_deployment,
    delete_all_namespace_deployments,
    monitor_deployments_to_completion,
    list_service_stage_deployments,
    cluster_service_url,
    expose_deployment_as_cluster_service,
    is_exposed_as_cluster_service,
    stop_exposing_cluster_service,
    ingress_route,
    create_deployment_ingress,
    delete_deployment_ingress,
    has_ingress,
)
from .utils import api_exception_msg, create_k8s_environment_variables, EnvVars


__all__ = [
    "cluster_role_binding_exists",
    "cluster_role_exists",
    "delete_cluster_role_binding",
    "workflow_cluster_role_binding_name",
    "load_kubernetes_config",
    "service_account_exists",
    "setup_job_and_deployment_service_accounts",
    "setup_workflow_service_account",
    "configure_workflow_cronjob",
    "create_workflow_job",
    "create_workflow_cronjob",
    "delete_workflow_cronjob",
    "list_workflow_cronjobs",
    "list_workflow_jobs",
    "JobStatus",
    "configure_workflow_job",
    "configure_batch_stage_job",
    "create_job",
    "delete_job",
    "monitor_jobs_to_completion",
    "namespace_exists",
    "create_namespace",
    "delete_namespace",
    "get_latest_pod_name",
    "get_pod_logs",
    "configure_env_vars_from_secrets",
    "secret_exists",
    "create_secret",
    "delete_secret",
    "list_secrets_in_namespace",
    "DeploymentStatus",
    "configure_service_stage_deployment",
    "create_deployment",
    "is_existing_deployment",
    "update_deployment",
    "rollback_deployment",
    "delete_deployment",
    "delete_all_namespace_deployments",
    "monitor_deployments_to_completion",
    "list_service_stage_deployments",
    "cluster_service_url",
    "expose_deployment_as_cluster_service",
    "is_exposed_as_cluster_service",
    "stop_exposing_cluster_service",
    "ingress_route",
    "create_deployment_ingress",
    "delete_deployment_ingress",
    "has_ingress",
    "api_exception_msg",
    "create_k8s_environment_variables",
    "EnvVars",
]
