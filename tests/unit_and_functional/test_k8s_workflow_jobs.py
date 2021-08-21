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
Unit tests for the high-level interface to the Kubernetes jobs and
cronjobs APIs, used to create and manage jobs that execute Bodywork
project workflows.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import kubernetes.client as k8s
from pytest import fixture

from bodywork.constants import (
    BODYWORK_WORKFLOW_JOB_TIME_TO_LIVE,
    BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
)
from bodywork.k8s.workflow_jobs import (
    configure_workflow_job,
    create_workflow_job,
    configure_workflow_cronjob,
    create_workflow_cronjob,
    delete_workflow_cronjob,
    list_workflow_cronjobs,
    list_workflow_jobs,
    update_workflow_cronjob,
)


@fixture(scope="session")
def workflow_job_object() -> k8s.V1Job:
    container = k8s.V1Container(
        name="bodywork",
        image="bodyworkml/bodywork-core:latest",
        image_pull_policy="Always",
        command=["bodywork", "workflow"],
        args=["bodywork-dev", "project_repo_url", "project_repo_branch"],
    )
    pod_spec = k8s.V1PodSpec(containers=[container], restart_policy="Never")
    pod_template_spec = k8s.V1PodTemplateSpec(spec=pod_spec)
    job_spec = k8s.V1JobSpec(
        template=pod_template_spec,
        completions=1,
        backoff_limit=2,
        ttl_seconds_after_finished=BODYWORK_WORKFLOW_JOB_TIME_TO_LIVE,
    )
    job = k8s.V1Job(
        metadata=k8s.V1ObjectMeta(
            name="bodywork-test-project", namespace="bodywork-dev"
        ),
        spec=job_spec,
    )
    return job


@patch("bodywork.k8s.workflow_jobs.random")
def test_configure_workflow_job(mock_random: MagicMock):
    mock_random.randint.return_value = 100
    job_definition = configure_workflow_job(
        namespace="bodywork-dev",
        project_repo_url="bodywork-ml/bodywork-test-project",
        project_repo_branch="dev",
        retries=2,
        image="bodyworkml/bodywork-core:0.0.7",
    )

    assert (
        f"bodywork-test-project-dev-{mock_random.randint()}"
        in job_definition.metadata.name
    )
    assert job_definition.metadata.namespace == "bodywork-dev"
    assert job_definition.spec.backoff_limit == 2
    assert (
        job_definition.spec.ttl_seconds_after_finished
        == BODYWORK_WORKFLOW_JOB_TIME_TO_LIVE
    )
    assert job_definition.spec.template.spec.containers[0].args == [
        "bodywork-ml/bodywork-test-project",
        "dev",
    ]
    assert (
        job_definition.spec.template.spec.containers[0].image
        == "bodyworkml/bodywork-core:0.0.7"
    )


@patch("bodywork.k8s.workflow_jobs.k8s.BatchV1Api")
def test_create_workflow_job_tries_to_create_workflow_job_with_k8s_api(
    mock_k8s_batchv1_api: MagicMock, workflow_job_object: k8s.V1Job
):
    create_workflow_job(workflow_job_object)
    mock_k8s_batchv1_api().create_namespaced_job.assert_called_once_with(
        body=workflow_job_object, namespace="bodywork-dev"
    )


@fixture(scope="session")
def workflow_cronjob_object() -> k8s.V1Job:
    container = k8s.V1Container(
        name="bodywork",
        image="bodyworkml/bodywork-core:latest",
        image_pull_policy="Always",
        command=["bodywork", "workflow"],
        args=["project_repo_url", "project_repo_branch"],
    )
    pod_spec = k8s.V1PodSpec(containers=[container], restart_policy="Never")
    pod_template_spec = k8s.V1PodTemplateSpec(spec=pod_spec)
    job_spec = k8s.V1JobSpec(template=pod_template_spec, completions=1, backoff_limit=2)
    job_template = k8s.V1beta1JobTemplateSpec(spec=job_spec)
    cronjob_spec = k8s.V1beta1CronJobSpec(
        schedule="0,30 * * * *",
        successful_jobs_history_limit=2,
        failed_jobs_history_limit=2,
        job_template=job_template,
    )
    cronjob = k8s.V1beta1CronJob(
        metadata=k8s.V1ObjectMeta(
            name="bodywork-test-project", namespace="bodywork-dev"
        ),
        spec=cronjob_spec,
        status=k8s.V1beta1CronJobStatus(last_schedule_time=datetime(2020, 9, 15)),
    )
    return cronjob


def test_configure_workflow_cronjob():
    cronjob_definition = configure_workflow_cronjob(
        cron_schedule="0,30 * * * *",
        namespace=BODYWORK_DEPLOYMENT_JOBS_NAMESPACE,
        project_repo_url="bodywork-ml/bodywork-test-project",
        project_repo_branch="dev",
        retries=2,
        successful_jobs_history_limit=2,
        failed_jobs_history_limit=2,
        image="bodyworkml/bodywork-core:0.0.7",
        job_name="test-job",
    )
    assert cronjob_definition.metadata.namespace == "bodywork-deployment-jobs"
    assert cronjob_definition.metadata.name == "test-job"
    assert cronjob_definition.spec.schedule == "0,30 * * * *"
    assert cronjob_definition.spec.successful_jobs_history_limit == 2
    assert cronjob_definition.spec.failed_jobs_history_limit == 2
    assert cronjob_definition.spec.job_template.spec.backoff_limit == 2
    assert cronjob_definition.spec.job_template.spec.template.spec.containers[
        0
    ].args == ["bodywork-ml/bodywork-test-project", "dev"]
    assert (
        cronjob_definition.spec.job_template.spec.template.spec.containers[0].image
        == "bodyworkml/bodywork-core:0.0.7"
    )


@patch("bodywork.k8s.workflow_jobs.k8s.BatchV1beta1Api")
def test_create_workflow_cronjob_tries_to_create_job_with_k8s_api(
    mock_k8s_batchv1beta1_api: MagicMock,
    workflow_cronjob_object: k8s.V1beta1CronJob,
):
    create_workflow_cronjob(workflow_cronjob_object)
    mock_k8s_batchv1beta1_api().create_namespaced_cron_job.assert_called_once_with(
        body=workflow_cronjob_object, namespace="bodywork-dev"
    )


@patch("bodywork.k8s.workflow_jobs.k8s.BatchV1beta1Api")
def test_updates_workflow_cronjob_updates_cronjob_with_k8s_api(
    mock_k8s_batchv1beta1_api: MagicMock,
):
    pod_spec = k8s.V1PodSpec(
        containers=[k8s.V1Container(name="bodywork", args=["fg", "test-branch"])],
    )
    job_spec = k8s.V1JobSpec(
        template=k8s.V1PodTemplateSpec(spec=pod_spec),
        backoff_limit=3,
    )
    job_template = k8s.V1beta1JobTemplateSpec(spec=k8s.V1Job(spec=job_spec).spec)
    expected_result = k8s.V1beta1CronJob(
        spec=k8s.V1beta1CronJobSpec(
            job_template=job_template,
            schedule="0 0 * * *",
            successful_jobs_history_limit=1,
            failed_jobs_history_limit=2,
        )
    )

    update_workflow_cronjob(
        "bodywork-ml", "test", "0 0 * * *", "fg", "test-branch", 3, 1, 2
    )

    mock_k8s_batchv1beta1_api().patch_namespaced_cron_job.assert_called_once_with(
        "test", "bodywork-ml", expected_result
    )


@patch("bodywork.k8s.workflow_jobs.k8s.BatchV1beta1Api")
def test_delete_workflow_cronjob_tries_to_delete_job_with_k8s_api(
    mock_k8s_batchv1beta1_api: MagicMock,
):
    delete_workflow_cronjob("bodywork-dev", "bodywork-test-project")
    mock_k8s_batchv1beta1_api().delete_namespaced_cron_job.assert_called_once_with(
        name="bodywork-test-project",
        namespace="bodywork-dev",
        body=k8s.V1DeleteOptions(propagation_policy="Background"),
    )


@patch("bodywork.k8s.workflow_jobs.k8s.BatchV1beta1Api")
def test_list_workflow_cronjobs_returns_cronjobs_summary_info(
    mock_k8s_batchv1beta1_api: MagicMock,
    workflow_cronjob_object: k8s.V1beta1CronJob,
):
    mock_k8s_batchv1beta1_api().list_namespaced_cron_job.return_value = (
        k8s.V1beta1CronJobList(items=[workflow_cronjob_object])
    )
    cronjobs = list_workflow_cronjobs("bodywork-dev")
    assert cronjobs["bodywork-test-project"]["schedule"] == "0,30 * * * *"
    assert cronjobs["bodywork-test-project"]["retries"] == 2
    assert cronjobs["bodywork-test-project"]["git_url"] == "project_repo_url"
    assert cronjobs["bodywork-test-project"]["git_branch"] == "project_repo_branch"
    assert cronjobs["bodywork-test-project"]["last_scheduled_time"] == datetime(
        2020, 9, 15
    )


@patch("bodywork.k8s.workflow_jobs.k8s.BatchV1Api")
def test_list_workflow_jobs_returns_jobs_summary_info(
    mock_k8s_batchv1_api: MagicMock,
):
    mock_k8s_batchv1_api().list_namespaced_job.return_value = k8s.V1JobList(
        items=[
            k8s.V1Job(
                metadata=k8s.V1ObjectMeta(name="workflow-job-12345"),
                status=k8s.V1JobStatus(
                    start_time=datetime(2020, 10, 19, 12, 15),
                    completion_time=None,
                    active=1,
                    succeeded=0,
                    failed=0,
                ),
            ),
            k8s.V1Job(
                metadata=k8s.V1ObjectMeta(name="workflow-job-6789"),
                status=k8s.V1JobStatus(
                    start_time=datetime(2020, 10, 19, 13, 15),
                    completion_time=datetime(2020, 10, 19, 13, 30),
                    active=0,
                    succeeded=1,
                    failed=0,
                ),
            ),
            k8s.V1Job(
                metadata=k8s.V1ObjectMeta(name="batch-job-12345"),
                status=k8s.V1JobStatus(
                    start_time=datetime(2020, 10, 19, 12, 16),
                    completion_time=datetime(2020, 10, 19, 12, 17),
                    active=0,
                    succeeded=1,
                    failed=0,
                ),
            ),
        ]
    )
    workflow_jobs = list_workflow_jobs("namespace", "workflow-job")
    assert len(workflow_jobs) == 2

    assert "workflow-job-12345" in workflow_jobs.keys()
    assert workflow_jobs["workflow-job-12345"]["start_time"] == datetime(
        2020, 10, 19, 12, 15
    )  # noqa
    assert workflow_jobs["workflow-job-12345"]["completion_time"] is None
    assert workflow_jobs["workflow-job-12345"]["active"] is True
    assert workflow_jobs["workflow-job-12345"]["succeeded"] is False
    assert workflow_jobs["workflow-job-12345"]["failed"] is False

    assert "workflow-job-6789" in workflow_jobs.keys()
    assert workflow_jobs["workflow-job-6789"]["start_time"] == datetime(
        2020, 10, 19, 13, 15
    )  # noqa
    assert workflow_jobs["workflow-job-6789"]["completion_time"] == datetime(
        2020, 10, 19, 13, 30
    )  # noqa
    assert workflow_jobs["workflow-job-6789"]["active"] is False
    assert workflow_jobs["workflow-job-6789"]["succeeded"] is True
    assert workflow_jobs["workflow-job-6789"]["failed"] is False
