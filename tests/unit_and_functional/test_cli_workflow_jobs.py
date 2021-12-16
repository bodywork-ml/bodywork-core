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
Test high-level workflow job management functions.
"""
from re import findall
from datetime import datetime
from unittest.mock import MagicMock, patch

from _pytest.capture import CaptureFixture
from bodywork.constants import BODYWORK_NAMESPACE

from bodywork.cli.workflow_jobs import (
    create_workflow_job,
    create_workflow_cronjob,
    delete_workflow_cronjob,
    display_cronjobs,
    display_workflow_job_history,
    display_workflow_job_logs,
    _is_existing_workflow_job,
    _is_existing_workflow_cronjob,
    _is_valid_cron_schedule,
    delete_workflow_job,
    update_workflow_cronjob,
)


@patch("bodywork.cli.workflow_jobs.k8s")
def test_is_existing_workflow_job(mock_k8s_module: MagicMock):
    mock_k8s_module.list_workflow_jobs.return_value = {"bodywork-test-project": {}}
    assert _is_existing_workflow_job("bodywork-dev", "bodywork-test-project") is True
    assert _is_existing_workflow_job("bodywork-dev", "not-a-real-cronjob") is False


@patch("bodywork.cli.workflow_jobs.k8s")
def test_create_workflow_job_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    create_workflow_job(
        "bodywork-dev",
        "bodywork-test-project",
        "project_repo_url",
        "project_repo_branch",
    )
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_jobs.return_value = {"bodywork-test-project": {}}
    create_workflow_job(
        "bodywork-dev",
        "bodywork-test-project",
        "project_repo_url",
        "project_repo_branch",
    )
    captured_two = capsys.readouterr()
    assert (
        "Cannot create workflow-job=bodywork-test-project as it already exists"
        in captured_two.out
    )

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_jobs.return_value = {"foo": {}}
    mock_k8s_module.create_workflow_job.side_effect = None
    create_workflow_job(
        "bodywork-dev",
        "bodywork-test-project",
        "project_repo_url",
        "project_repo_branch",
    )
    captured_three = capsys.readouterr()
    assert "Created workflow-job=bodywork-test-project" in captured_three.out


@patch("bodywork.cli.workflow_jobs.k8s")
def test_delete_workflow_job_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    delete_workflow_job("bodywork-dev", "bodywork-test-project")
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_jobs.return_value = {"foo": {}}
    delete_workflow_job("bodywork-dev", "bodywork-test-project")
    captured_two = capsys.readouterr()
    assert "Could not find workflow-job=bodywork-test-project" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_jobs.return_value = {"bodywork-test-project": {}}
    mock_k8s_module.delete_job.side_effect = None
    delete_workflow_job("bodywork-dev", "bodywork-test-project")
    captured_three = capsys.readouterr()
    assert "Deleted workflow-job=bodywork-test-project" in captured_three.out


@patch("bodywork.cli.workflow_jobs.k8s")
def test_is_existing_workflow_cronjob(mock_k8s_module: MagicMock):
    mock_k8s_module.list_workflow_cronjobs.return_value = {"bodywork-test-project": {}}
    assert (
        _is_existing_workflow_cronjob("bodywork-dev", "bodywork-test-project") is True
    )
    assert _is_existing_workflow_cronjob("bodywork-dev", "not-a-real-cronjob") is False


def test_is_valid_cron_scheule():
    assert _is_valid_cron_schedule("* * * *") is False
    assert _is_valid_cron_schedule("* * * * *") is True

    assert _is_valid_cron_schedule("a * * * *") is False
    assert _is_valid_cron_schedule("* a * * *") is False
    assert _is_valid_cron_schedule("* * a * *") is False
    assert _is_valid_cron_schedule("* * * a *") is False
    assert _is_valid_cron_schedule("* * * * a") is False

    assert _is_valid_cron_schedule("0 * * * *") is True
    assert _is_valid_cron_schedule("60 * * * *") is False
    assert _is_valid_cron_schedule("*/5 * * * *") is True
    assert _is_valid_cron_schedule("5/5 * * * *") is False
    assert _is_valid_cron_schedule("0,15,30 * * * *") is True
    assert _is_valid_cron_schedule("0,15,30/5 * * * *") is False
    assert _is_valid_cron_schedule("15-45 * * * *") is True
    assert _is_valid_cron_schedule("15-30-45 * * * *") is False
    assert _is_valid_cron_schedule("15,30,30-45 * * * *") is False
    assert _is_valid_cron_schedule("15-45/5 * * * *") is True

    assert _is_valid_cron_schedule("* 0 * * *") is True
    assert _is_valid_cron_schedule("* 24 * * *") is False
    assert _is_valid_cron_schedule("* */5 * * *") is True
    assert _is_valid_cron_schedule("* 5/5 * * *") is False
    assert _is_valid_cron_schedule("* 0,6,12 * * *") is True
    assert _is_valid_cron_schedule("* 0,12/5 * * *") is False
    assert _is_valid_cron_schedule("* 6-18 * * *") is True
    assert _is_valid_cron_schedule("* 6-12-18 * * *") is False
    assert _is_valid_cron_schedule("* 6,12,18-22 * * *") is False
    assert _is_valid_cron_schedule("* 6-18/5 * * *") is True

    assert _is_valid_cron_schedule("* * 0 * *") is True
    assert _is_valid_cron_schedule("* * 32 * *") is False
    assert _is_valid_cron_schedule("* * */2 * *") is True
    assert _is_valid_cron_schedule("* * 2/2 * *") is False
    assert _is_valid_cron_schedule("* * 0,6,12 * *") is True
    assert _is_valid_cron_schedule("* * 0,12/2 * *") is False
    assert _is_valid_cron_schedule("* * 6-18 * *") is True
    assert _is_valid_cron_schedule("* * 6-12-18 * *") is False
    assert _is_valid_cron_schedule("* * 6,12,18-22 * *") is False
    assert _is_valid_cron_schedule("* * 6-18/5 * *") is True

    assert _is_valid_cron_schedule("* * * 0 *") is True
    assert _is_valid_cron_schedule("* * * 13 *") is False
    assert _is_valid_cron_schedule("* * * */3 *") is True
    assert _is_valid_cron_schedule("* * * 3/3 *") is False
    assert _is_valid_cron_schedule("* * * 0,6,12 *") is True
    assert _is_valid_cron_schedule("* * * 0,12/2 *") is False
    assert _is_valid_cron_schedule("* * * 6-12 *") is True
    assert _is_valid_cron_schedule("* * * 3-6-12 *") is False
    assert _is_valid_cron_schedule("* * * 3,6,10-12 *") is False
    assert _is_valid_cron_schedule("* * * 6-12/3 *") is True

    assert _is_valid_cron_schedule("* * * * 0") is True
    assert _is_valid_cron_schedule("* * * * 7") is False
    assert _is_valid_cron_schedule("* * * * */1") is True
    assert _is_valid_cron_schedule("* * * * 1/1") is False
    assert _is_valid_cron_schedule("* * * * 0,2,4") is True
    assert _is_valid_cron_schedule("* * * * 0,4/2") is False
    assert _is_valid_cron_schedule("* * * * 0-5") is True
    assert _is_valid_cron_schedule("* * * * 0-2-4") is False
    assert _is_valid_cron_schedule("* * * * 0,1,2-3") is False
    assert _is_valid_cron_schedule("* * * * 0-4/2") is True


@patch("bodywork.cli.workflow_jobs.k8s")
def test_create_workflow_cronjob(mock_k8s_module: MagicMock, capsys: CaptureFixture):
    mock_k8s_module.namespace_exists.return_value = False
    create_workflow_cronjob(
        BODYWORK_NAMESPACE,
        "0 * * * *",
        "bodywork-test-project",
        "project_repo_url",
        "project_repo_branch",
    )
    captured_one = capsys.readouterr()
    assert (
        f"Could not find namespace={BODYWORK_NAMESPACE} on k8s cluster"
        in captured_one.out
    )

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {"bodywork-test-project": {}}
    create_workflow_cronjob(
        BODYWORK_NAMESPACE,
        "0 * * * *",
        "bodywork-test-project",
        "project_repo_url",
        "project_repo_branch",
    )
    captured_two = capsys.readouterr()
    assert (
        "Cannot create cronjob=bodywork-test-project as it already exists"
        in captured_two.out
    )

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {"foo": {}}
    mock_k8s_module.create_workflow_cronjob.side_effect = None
    create_workflow_cronjob(
        BODYWORK_NAMESPACE,
        "0 * * *",
        "bodywork-test-project",
        "project_repo_url",
        "project_repo_branch",
    )
    captured_three = capsys.readouterr()
    assert "Invalid cronjob schedule: 0 * * *" in captured_three.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {"foo": {}}
    mock_k8s_module.create_workflow_cronjob.side_effect = None
    create_workflow_cronjob(
        BODYWORK_NAMESPACE,
        "0 * * * *",
        "bodywork-test-project",
        "project_repo_url",
        "project_repo_branch",
    )
    captured_four = capsys.readouterr()
    assert "Created cronjob=bodywork-test-project" in captured_four.out


@patch("bodywork.cli.workflow_jobs.k8s")
def test_update_cronjob_validation(mock_k8s_module: MagicMock, capsys: CaptureFixture):
    mock_k8s_module.namespace_exists.return_value = False
    update_workflow_cronjob(
        "bodywork-dev", "test", "0 0 * * *", "fg", "test-branch", 3, 1
    )
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster." in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_jobs.return_value = {"bodywork-test-project": {}}
    update_workflow_cronjob(
        "bodywork-dev", "test", "0 0 * * *", "fg", "test-branch", 3, 1
    )
    captured_two = capsys.readouterr()
    assert "Could not find cronjob=test" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {"test": {}}

    update_workflow_cronjob(
        "bodywork-dev", "test", "0 * * *", "fg", "test-branch", 3, 1
    )

    captured_three = capsys.readouterr()
    assert "Invalid cronjob schedule: 0 * * *" in captured_three.out


@patch("bodywork.cli.workflow_jobs.k8s")
def test_update_cronjob(mock_k8s_module: MagicMock, capsys: CaptureFixture):
    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {"test": {}}

    update_workflow_cronjob(
        "bodywork-dev", "test", "0 * * * *", "fg", "test-branch", 3, 1
    )

    captured_one = capsys.readouterr()
    assert "Updated cronjob=test" in captured_one.out


@patch("bodywork.cli.workflow_jobs.k8s")
def test_delete_workflow_cronjob_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    delete_workflow_cronjob("bodywork-dev", "bodywork-test-project")
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {"foo": {}}
    delete_workflow_cronjob("bodywork-dev", "bodywork-test-project")
    captured_two = capsys.readouterr()
    assert "Could not find cronjob=bodywork-test-project" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {"bodywork-test-project": {}}
    mock_k8s_module.delete_workflow_cronjob.side_effect = None
    delete_workflow_cronjob("bodywork-dev", "bodywork-test-project")
    captured_three = capsys.readouterr()
    assert "Deleted cronjob=bodywork-test-project" in captured_three.out


@patch("bodywork.cli.workflow_jobs.k8s")
def test_display_workflow_cronjobs_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_cronjobs("bodywork-dev")
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {
        "bodywork-test-project": {
            "schedule": "0 * * * *",
            "last_scheduled_time": datetime(2020, 9, 15),
            "retries": 2,
            "git_url": "project_repo_url",
            "git_branch": "project_repo_branch",
        }
    }
    display_cronjobs("bodywork-dev")
    captured_two = capsys.readouterr()
    assert findall(r"bodywork-test-project.+project_repo_url", captured_two.out)

    display_cronjobs("bodywork-dev", "bodywork-test-project")
    captured_three = capsys.readouterr()
    assert findall(r"schedule.+0 * * * *", captured_three.out)
    assert findall(r"last_scheduled_time.+2020-09-15 00:00:00", captured_three.out)
    assert findall(r"retries.+2", captured_three.out)
    assert findall(r"git_url.+project_repo_url", captured_three.out)
    assert findall(r"git_branch.+project_repo_branch", captured_three.out)


@patch("bodywork.cli.workflow_jobs.k8s")
def test_display_workflow_job_history(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_workflow_job_history("bodywork-dev", "bodywork-test-project")
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_jobs.return_value = {
        "workflow-job-12345": {
            "start_time": datetime(2020, 10, 19, 1, 15),
            "completion_time": datetime(2020, 10, 19, 1, 30),
            "active": False,
            "succeeded": True,
            "failed": False,
        }
    }
    display_workflow_job_history("bodywork-dev", "bodywork-test-project")
    captured_two = capsys.readouterr()
    assert findall(r"start_time.+2020-10-19 01:15:00", captured_two.out)
    assert findall(r"completion_time.+2020-10-19 01:30:00", captured_two.out)
    assert findall(r"active.+False", captured_two.out)
    assert findall(r"succeeded.+True", captured_two.out)
    assert findall(r"failed.+False", captured_two.out)


@patch("bodywork.cli.workflow_jobs.k8s")
def test_display_cronjob_workflow_job_logs(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_workflow_job_logs("bodywork-dev", "bodywork-test-project-12345")
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.get_latest_pod_name.return_value = None
    display_workflow_job_logs("bodywork-dev", "bodywork-test-project-12345")
    captured_two = capsys.readouterr()
    assert "find pod for workflow job=bodywork-test-project-12345" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.get_latest_pod_name.return_value = (
        "bodywork-test-project-12345-pqrs"
    )
    mock_k8s_module.get_pod_logs.return_value = "INFO - foo.py - bar"
    display_workflow_job_logs("bodywork-dev", "bodywork-test-project-12345")
    captured_three = capsys.readouterr()
    assert "INFO - foo.py - bar" in captured_three.out
