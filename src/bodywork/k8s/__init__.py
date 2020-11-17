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
    setup_workflow_service_account
)
from .cronjobs import (
    configure_cronjob,
    create_cronjob,
    delete_cronjob,
    list_cronjobs,
    list_workflow_jobs
)
from .jobs import (
    JobStatus,
    configure_batch_stage_job,
    create_job,
    delete_job,
    monitor_jobs_to_completion
)
from .namespaces import (
    namespace_exists,
    create_namespace,
    delete_namespace
)
from .pod_logs import (
    get_latest_pod_name,
    get_pod_logs
)
from .secrets import (
    configure_env_vars_from_secrets,
    secret_exists,
    create_secret,
    delete_secret,
    list_secrets_in_namespace
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
    expose_deployment_as_cluster_service,
    is_exposed_as_cluster_service,
    stop_exposing_cluster_service
)
from .utils import (
    api_exception_msg
)


__all__ = [
    'cluster_role_binding_exists',
    'cluster_role_exists',
    'delete_cluster_role_binding',
    'workflow_cluster_role_binding_name',
    'load_kubernetes_config',
    'service_account_exists',
    'setup_job_and_deployment_service_accounts',
    'setup_workflow_service_account',
    'configure_cronjob',
    'create_cronjob',
    'delete_cronjob',
    'list_cronjobs',
    'list_workflow_jobs',
    'JobStatus',
    'configure_batch_stage_job',
    'create_job',
    'delete_job',
    'monitor_jobs_to_completion',
    'namespace_exists',
    'create_namespace',
    'delete_namespace',
    'get_latest_pod_name',
    'get_pod_logs',
    'configure_env_vars_from_secrets',
    'secret_exists',
    'create_secret',
    'delete_secret',
    'list_secrets_in_namespace',
    'DeploymentStatus',
    'configure_service_stage_deployment',
    'create_deployment',
    'is_existing_deployment',
    'update_deployment',
    'rollback_deployment',
    'delete_deployment',
    'delete_all_namespace_deployments',
    'monitor_deployments_to_completion',
    'list_service_stage_deployments',
    'expose_deployment_as_cluster_service',
    'is_exposed_as_cluster_service',
    'stop_exposing_cluster_service',
    'api_exception_msg'
]
