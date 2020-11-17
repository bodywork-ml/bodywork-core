"""
Unit tests for the high-level Kubernetes jobs interface, used to
orchestrate the execution of batch stages.
"""
from unittest.mock import MagicMock, patch

import kubernetes
from pytest import fixture, raises

from bodywork.exceptions import BodyworkJobFailure
from bodywork.k8s.jobs import (
    configure_batch_stage_job,
    create_job,
    delete_job,
    _get_job_status,
    JobStatus,
    monitor_jobs_to_completion,
)


@fixture(scope='session')
def batch_stage_job_object() -> kubernetes.client.V1Job:
    container_resources = kubernetes.client.V1ResourceRequirements(
        requests={'cpu': '0.5', 'memory': '250M'}
    )
    container = kubernetes.client.V1Container(
        name='bodywork',
        image='alexioannides/bodywork:latest',
        image_pull_policy='Always',
        resources=container_resources,
        command=['bodywork', 'stage'],
        args=['project_repo_url', 'project_repo_branch', 'train']
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
        backoff_limit=4
    )
    job_metadata = kubernetes.client.V1ObjectMeta(
        namespace='bodywork-dev',
        name='bodywork-test-project--train'
    )
    job = kubernetes.client.V1Job(
        metadata=job_metadata,
        spec=job_spec
    )
    return job


def test_configure_batch_stage_job():
    job = configure_batch_stage_job(
        namespace='bodywork-dev',
        stage_name='train',
        project_name='bodywork-test-project',
        project_repo_url='alexioannides/bodywork-test-project',
        project_repo_branch='dev',
        image='alexioannides/bodywork:0.0.7',
        cpu_request=1,
        memory_request=100,
        retries=2
    )
    assert job.metadata.namespace == 'bodywork-dev'
    assert job.metadata.name == 'bodywork-test-project--train'
    assert job.spec.backoff_limit == 2
    assert (job.spec.template.spec.containers[0].args
            == ['alexioannides/bodywork-test-project', 'dev', 'train'])
    assert (job.spec.template.spec.containers[0].image
            == 'alexioannides/bodywork:0.0.7')
    assert job.spec.template.spec.containers[0].resources.requests['cpu'] == '1'
    assert job.spec.template.spec.containers[0].resources.requests['memory'] == '100M'


@patch('kubernetes.client.BatchV1Api')
def test_create_job_tries_to_create_job_with_k8s_api(
    mock_k8s_batch_api: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    create_job(batch_stage_job_object)
    mock_k8s_batch_api().create_namespaced_job.assert_called_once_with(
        body=batch_stage_job_object,
        namespace='bodywork-dev'
    )


@patch('kubernetes.client.BatchV1Api')
def test_delete_job_tries_to_create_job_with_k8s_api(
    mock_k8s_batch_api: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    delete_job(
        batch_stage_job_object.metadata.namespace,
        batch_stage_job_object.metadata.name
    )
    mock_k8s_batch_api().delete_namespaced_job.assert_called_once_with(
        name='bodywork-test-project--train',
        namespace='bodywork-dev',
        body=kubernetes.client.V1DeleteOptions(propagation_policy='Background')
    )


@patch('kubernetes.client.BatchV1Api')
def test_get_job_status_correctly_determines_active_status(
    mock_k8s_batch_api: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_k8s_batch_api().list_namespaced_job.return_value = (
        kubernetes.client.V1JobList(
            items=[
                kubernetes.client.V1Job(
                    status=kubernetes.client.V1JobStatus(active=1)
                )
            ]
        )
    )
    assert _get_job_status(batch_stage_job_object) == JobStatus.ACTIVE


@patch('kubernetes.client.BatchV1Api')
def test_get_job_status_correctly_determines_succeeded_status(
    mock_k8s_batch_api: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_k8s_batch_api().list_namespaced_job.return_value = (
        kubernetes.client.V1JobList(
            items=[
                kubernetes.client.V1Job(
                    status=kubernetes.client.V1JobStatus(succeeded=1)
                )
            ]
        )
    )
    assert _get_job_status(batch_stage_job_object) == JobStatus.SUCCEEDED


@patch('kubernetes.client.BatchV1Api')
def test_get_job_status_correctly_determines_failed_status(
    mock_k8s_batch_api: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_k8s_batch_api().list_namespaced_job.return_value = (
        kubernetes.client.V1JobList(
            items=[
                kubernetes.client.V1Job(
                    status=kubernetes.client.V1JobStatus(failed=1)
                )
            ]
        )
    )
    assert _get_job_status(batch_stage_job_object) == JobStatus.FAILED


@patch('kubernetes.client.BatchV1Api')
def test_get_job_status_raises_exception_when_status_cannot_be_determined(
    mock_k8s_batch_api: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_k8s_batch_api().list_namespaced_job.return_value = (
        kubernetes.client.V1JobList(
            items=[
                kubernetes.client.V1Job(
                    status=kubernetes.client.V1JobStatus(active='maybe')
                )
            ]
        )
    )
    with raises(RuntimeError, match='cannot determine status'):
        _get_job_status(batch_stage_job_object)


@patch('kubernetes.client.BatchV1Api')
def test_get_job_status_raises_exception_when_job_cannot_be_found(
    mock_k8s_batch_api: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_k8s_batch_api().list_namespaced_job.return_value = (
        kubernetes.client.V1JobList(items=[])
    )
    with raises(RuntimeError, match='cannot find job'):
        _get_job_status(batch_stage_job_object)


@patch('bodywork.k8s.jobs._get_job_status')
def test_monitor_jobs_to_completion_raises_timeout_error_if_jobs_do_not_succeed(
    mock_job_status: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_job_status.return_value = JobStatus.ACTIVE
    with raises(TimeoutError, match='have yet to reach status=succeeded'):
        monitor_jobs_to_completion([batch_stage_job_object], timeout_seconds=1)


@patch('bodywork.k8s.jobs._get_job_status')
def test_monitor_jobs_to_completion_raises_bodyworkjobfailures_error_if_jobs_fail(
    mock_job_status: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_job_status.return_value = JobStatus.FAILED
    with raises(BodyworkJobFailure, match='have failed'):
        monitor_jobs_to_completion([batch_stage_job_object], timeout_seconds=1)


@patch('bodywork.k8s.jobs._get_job_status')
def test_monitor_jobs_to_completion_identifies_successful_jobs(
    mock_job_status: MagicMock,
    batch_stage_job_object: kubernetes.client.V1Job
):
    mock_job_status.side_effect = [
        JobStatus.ACTIVE,
        JobStatus.ACTIVE,
        JobStatus.SUCCEEDED,
        JobStatus.SUCCEEDED
    ]
    successful = monitor_jobs_to_completion(
        [batch_stage_job_object, batch_stage_job_object],
        timeout_seconds=1,
        polling_freq_seconds=0.5
    )
    assert successful is True
