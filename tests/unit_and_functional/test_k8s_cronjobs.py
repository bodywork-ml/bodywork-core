"""
Unit tests for the high-level Kubernetes cronjobs interface, used to
to create and manage cronjobs that execute Bodywork project workflows.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import kubernetes
from pytest import fixture

from bodywork.k8s.cronjobs import (
    configure_cronjob,
    create_cronjob,
    delete_cronjob,
    list_cronjobs,
    list_workflow_jobs
)


@fixture(scope='session')
def cronjob_object() -> kubernetes.client.V1Job:
    container = kubernetes.client.V1Container(
        name='bodywork',
        image='bodyworkml/bodywork-core:latest',
        image_pull_policy='Always',
        command=['bodywork', 'workflow'],
        args=['bodywork-dev', 'project_repo_url', 'project_repo_branch']
    )
    pod_spec = kubernetes.client.V1PodSpec(
        containers=[container],
        restart_policy='Never'
    )
    pod_template_spec = kubernetes.client.V1PodTemplateSpec(
        spec=pod_spec
    )
    job_spec = kubernetes.client.V1JobSpec(
        template=pod_template_spec,
        completions=1,
        backoff_limit=2
    )
    job_template = kubernetes.client.V1beta1JobTemplateSpec(
        spec=job_spec
    )
    cronjob_spec = kubernetes.client.V1beta1CronJobSpec(
        schedule='0,30 * * * *',
        successful_jobs_history_limit=2,
        failed_jobs_history_limit=2,
        job_template=job_template
    )
    cronjob = kubernetes.client.V1beta1CronJob(
        metadata=kubernetes.client.V1ObjectMeta(
            name='bodywork-test-project',
            namespace='bodywork-dev'
        ),
        spec=cronjob_spec,
        status=kubernetes.client.V1beta1CronJobStatus(
            last_schedule_time=datetime(2020, 9, 15)
        )
    )
    return cronjob


def test_configure_batch_stage_cronjob():
    cronjob_definition = configure_cronjob(
        cron_schedule='0,30 * * * *',
        namespace='bodywork-dev',
        project_name='bodywork-test-project',
        project_repo_url='bodywork-ml/bodywork-test-project',
        project_repo_branch='dev',
        retries=2,
        successful_jobs_history_limit=2,
        failed_jobs_history_limit=2,
        image='bodyworkml/bodywork-core:0.0.7',
    )
    assert cronjob_definition.metadata.namespace == 'bodywork-dev'
    assert cronjob_definition.metadata.name == 'bodywork-test-project'
    assert cronjob_definition.spec.schedule == '0,30 * * * *'
    assert cronjob_definition.spec.successful_jobs_history_limit == 2
    assert cronjob_definition.spec.failed_jobs_history_limit == 2
    assert cronjob_definition.spec.job_template.spec.backoff_limit == 2
    assert (cronjob_definition.spec.job_template.spec.template.spec.containers[0].args
            == ['--namespace=bodywork-dev', 'bodywork-ml/bodywork-test-project', 'dev'])
    assert (cronjob_definition.spec.job_template.spec.template.spec.containers[0].image
            == 'bodyworkml/bodywork-core:0.0.7')


@patch('kubernetes.client.BatchV1beta1Api')
def test_create_cronjob_tries_to_create_job_with_k8s_api(
    mock_k8s_batchv1beta1_api: MagicMock,
    cronjob_object: kubernetes.client.V1beta1CronJob
):
    create_cronjob(cronjob_object)
    mock_k8s_batchv1beta1_api().create_namespaced_cron_job.assert_called_once_with(
        body=cronjob_object,
        namespace='bodywork-dev'
    )


@patch('kubernetes.client.BatchV1beta1Api')
def test_delete_cronjob_tries_to_delete_job_with_k8s_api(
    mock_k8s_batchv1beta1_api: MagicMock,
    cronjob_object: kubernetes.client.V1beta1CronJob
):
    delete_cronjob('bodywork-dev', 'bodywork-test-project')
    mock_k8s_batchv1beta1_api().delete_namespaced_cron_job.assert_called_once_with(
        name='bodywork-test-project',
        namespace='bodywork-dev',
        body=kubernetes.client.V1DeleteOptions(propagation_policy='Background')
    )


@patch('kubernetes.client.BatchV1beta1Api')
def test_list_cronjobs_returns_cronjobs_summary_info(
    mock_k8s_batchv1beta1_api: MagicMock,
    cronjob_object: kubernetes.client.V1beta1CronJob
):
    mock_k8s_batchv1beta1_api().list_namespaced_cron_job.return_value = (
        kubernetes.client.V1beta1CronJobList(items=[cronjob_object])
    )
    cronjobs = list_cronjobs('bodywork-dev')
    assert cronjobs['bodywork-test-project']['schedule'] == '0,30 * * * *'
    assert cronjobs['bodywork-test-project']['git_url'] == 'project_repo_url'
    assert cronjobs['bodywork-test-project']['git_branch'] == 'project_repo_branch'
    assert (cronjobs['bodywork-test-project']['last_scheduled_time']
            == datetime(2020, 9, 15))


@patch('kubernetes.client.BatchV1Api')
def test_list_cronjobs_workflow_jobs(
    mock_k8s_batchv1_api: MagicMock,
):
    mock_k8s_batchv1_api().list_namespaced_job.return_value = (
        kubernetes.client.V1JobList(
            items=[
                kubernetes.client.V1Job(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='workflow-job-12345'
                    ),
                    status=kubernetes.client.V1JobStatus(
                        start_time=datetime(2020, 10, 19, 12, 15),
                        completion_time=None,
                        active=1,
                        succeeded=0,
                        failed=0
                    )
                ),
                kubernetes.client.V1Job(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='workflow-job-6789'
                    ),
                    status=kubernetes.client.V1JobStatus(
                        start_time=datetime(2020, 10, 19, 13, 15),
                        completion_time=datetime(2020, 10, 19, 13, 30),
                        active=0,
                        succeeded=1,
                        failed=0
                    )
                ),
                kubernetes.client.V1Job(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name='batch-job-12345'
                    ),
                    status=kubernetes.client.V1JobStatus(
                        start_time=datetime(2020, 10, 19, 12, 16),
                        completion_time=datetime(2020, 10, 19, 12, 17),
                        active=0,
                        succeeded=1,
                        failed=0
                    )
                )
            ]
        )
    )
    workflow_jobs = list_workflow_jobs('namespace', 'workflow-job')
    assert len(workflow_jobs) == 2

    assert 'workflow-job-12345' in workflow_jobs.keys()
    assert (workflow_jobs['workflow-job-12345']['start_time'] == datetime(2020, 10, 19, 12, 15))  # noqa
    assert workflow_jobs['workflow-job-12345']['completion_time'] is None
    assert workflow_jobs['workflow-job-12345']['active'] is True
    assert workflow_jobs['workflow-job-12345']['succeeded'] is False
    assert workflow_jobs['workflow-job-12345']['failed'] is False

    assert 'workflow-job-6789' in workflow_jobs.keys()
    assert workflow_jobs['workflow-job-6789']['start_time'] == datetime(2020, 10, 19, 13, 15)  # noqa
    assert workflow_jobs['workflow-job-6789']['completion_time'] == datetime(2020, 10, 19, 13, 30)  # noqa
    assert workflow_jobs['workflow-job-6789']['active'] is False
    assert workflow_jobs['workflow-job-6789']['succeeded'] is True
    assert workflow_jobs['workflow-job-6789']['failed'] is False
