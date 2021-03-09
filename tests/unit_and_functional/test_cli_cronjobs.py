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
Test high-level cronjob management functions.
"""
import re
from datetime import datetime
from unittest.mock import MagicMock, patch

from _pytest.capture import CaptureFixture

from bodywork.cli.cronjobs import (
    create_workflow_cronjob_in_namespace,
    delete_workflow_cronjob_in_namespace,
    display_cronjobs_in_namespace,
    display_cronjob_workflow_history,
    display_cronjob_workflow_logs,
    _is_existing_cronjob,
    _is_valid_cron_schedule
)


@patch('bodywork.cli.cronjobs.k8s')
def test_is_existing_cronjob(mock_k8s_module: MagicMock):
    mock_k8s_module.list_workflow_cronjobs.return_value = {
        'bodywork-test-project': {}
    }
    assert _is_existing_cronjob('bodywork-dev', 'bodywork-test-project') is True
    assert _is_existing_cronjob('bodywork-dev', 'not-a-real-cronjob') is False


def test_is_valid_cron_scheule():
    assert _is_valid_cron_schedule('* * * *') is False
    assert _is_valid_cron_schedule('* * * * *') is True

    assert _is_valid_cron_schedule('a * * * *') is False
    assert _is_valid_cron_schedule('* a * * *') is False
    assert _is_valid_cron_schedule('* * a * *') is False
    assert _is_valid_cron_schedule('* * * a *') is False
    assert _is_valid_cron_schedule('* * * * a') is False

    assert _is_valid_cron_schedule('0 * * * *') is True
    assert _is_valid_cron_schedule('60 * * * *') is False
    assert _is_valid_cron_schedule('*/5 * * * *') is True
    assert _is_valid_cron_schedule('5/5 * * * *') is False
    assert _is_valid_cron_schedule('0,15,30 * * * *') is True
    assert _is_valid_cron_schedule('0,15,30/5 * * * *') is False
    assert _is_valid_cron_schedule('15-45 * * * *') is True
    assert _is_valid_cron_schedule('15-30-45 * * * *') is False
    assert _is_valid_cron_schedule('15,30,30-45 * * * *') is False
    assert _is_valid_cron_schedule('15-45/5 * * * *') is True

    assert _is_valid_cron_schedule('* 0 * * *') is True
    assert _is_valid_cron_schedule('* 24 * * *') is False
    assert _is_valid_cron_schedule('* */5 * * *') is True
    assert _is_valid_cron_schedule('* 5/5 * * *') is False
    assert _is_valid_cron_schedule('* 0,6,12 * * *') is True
    assert _is_valid_cron_schedule('* 0,12/5 * * *') is False
    assert _is_valid_cron_schedule('* 6-18 * * *') is True
    assert _is_valid_cron_schedule('* 6-12-18 * * *') is False
    assert _is_valid_cron_schedule('* 6,12,18-22 * * *') is False
    assert _is_valid_cron_schedule('* 6-18/5 * * *') is True

    assert _is_valid_cron_schedule('* * 0 * *') is True
    assert _is_valid_cron_schedule('* * 32 * *') is False
    assert _is_valid_cron_schedule('* * */2 * *') is True
    assert _is_valid_cron_schedule('* * 2/2 * *') is False
    assert _is_valid_cron_schedule('* * 0,6,12 * *') is True
    assert _is_valid_cron_schedule('* * 0,12/2 * *') is False
    assert _is_valid_cron_schedule('* * 6-18 * *') is True
    assert _is_valid_cron_schedule('* * 6-12-18 * *') is False
    assert _is_valid_cron_schedule('* * 6,12,18-22 * *') is False
    assert _is_valid_cron_schedule('* * 6-18/5 * *') is True

    assert _is_valid_cron_schedule('* * * 0 *') is True
    assert _is_valid_cron_schedule('* * * 13 *') is False
    assert _is_valid_cron_schedule('* * * */3 *') is True
    assert _is_valid_cron_schedule('* * * 3/3 *') is False
    assert _is_valid_cron_schedule('* * * 0,6,12 *') is True
    assert _is_valid_cron_schedule('* * * 0,12/2 *') is False
    assert _is_valid_cron_schedule('* * * 6-12 *') is True
    assert _is_valid_cron_schedule('* * * 3-6-12 *') is False
    assert _is_valid_cron_schedule('* * * 3,6,10-12 *') is False
    assert _is_valid_cron_schedule('* * * 6-12/3 *') is True

    assert _is_valid_cron_schedule('* * * * 0') is True
    assert _is_valid_cron_schedule('* * * * 7') is False
    assert _is_valid_cron_schedule('* * * * */1') is True
    assert _is_valid_cron_schedule('* * * * 1/1') is False
    assert _is_valid_cron_schedule('* * * * 0,2,4') is True
    assert _is_valid_cron_schedule('* * * * 0,4/2') is False
    assert _is_valid_cron_schedule('* * * * 0-5') is True
    assert _is_valid_cron_schedule('* * * * 0-2-4') is False
    assert _is_valid_cron_schedule('* * * * 0,1,2-3') is False
    assert _is_valid_cron_schedule('* * * * 0-4/2') is True


@patch('bodywork.cli.cronjobs.k8s')
def test_create_workflow_cronjob_in_namespace(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    create_workflow_cronjob_in_namespace(
        'bodywork-dev',
        '0 * * * *',
        'bodywork-test-project',
        'project_repo_url',
        'project_repo_branch'
    )
    captured_one = capsys.readouterr()
    assert 'namespace=bodywork-dev could not be found' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {'bodywork-test-project': {}}
    create_workflow_cronjob_in_namespace(
        'bodywork-dev',
        '0 * * * *',
        'bodywork-test-project',
        'project_repo_url',
        'project_repo_branch'
    )
    captured_two = capsys.readouterr()
    assert 'cronjob=bodywork-test-project already exists' in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {'foo': {}}
    mock_k8s_module.create_workflow_cronjob.side_effect = None
    create_workflow_cronjob_in_namespace(
        'bodywork-dev',
        '0 * * *',
        'bodywork-test-project',
        'project_repo_url',
        'project_repo_branch'
    )
    captured_three = capsys.readouterr()
    assert 'schedule=0 * * * is not a valid cron schedule' in captured_three.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {'foo': {}}
    mock_k8s_module.create_workflow_cronjob.side_effect = None
    create_workflow_cronjob_in_namespace(
        'bodywork-dev',
        '0 * * * *',
        'bodywork-test-project',
        'project_repo_url',
        'project_repo_branch'
    )
    captured_four = capsys.readouterr()
    assert 'cronjob=bodywork-test-project created in namespace' in captured_four.out


@patch('bodywork.cli.cronjobs.k8s')
def test_delete_workflow_cronjob_in_namespace(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    delete_workflow_cronjob_in_namespace('bodywork-dev', 'bodywork-test-project')
    captured_one = capsys.readouterr()
    assert 'namespace=bodywork-dev could not be found' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {'foo': {}}
    delete_workflow_cronjob_in_namespace('bodywork-dev', 'bodywork-test-project')
    captured_two = capsys.readouterr()
    assert 'cronjob=bodywork-test-project not found' in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {'bodywork-test-project': {}}
    mock_k8s_module.delete_workflow_cronjob.side_effect = None
    delete_workflow_cronjob_in_namespace('bodywork-dev', 'bodywork-test-project')
    captured_three = capsys.readouterr()
    assert 'cronjob=bodywork-test-project deleted from namespace' in captured_three.out


@patch('bodywork.cli.cronjobs.k8s')
def test_display_cronjobs_in_namespace(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_cronjobs_in_namespace('bodywork-dev')
    captured_one = capsys.readouterr()
    assert 'namespace=bodywork-dev could not be found' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_cronjobs.return_value = {
        'bodywork-test-project': {
            'schedule': '0 * * * *',
            'last_scheduled_time': datetime(2020, 9, 15),
            'retries': 2,
            'git_url': 'project_repo_url',
            'git_branch': 'project_repo_branch'
        }
    }
    display_cronjobs_in_namespace('bodywork-dev')
    captured_two = capsys.readouterr()
    assert re.findall(r'bodywork-test-project', captured_two.out)
    assert re.findall(r'SCHEDULE\s+0 * * * *', captured_two.out)
    assert re.findall(r'RETRIES\s+2', captured_two.out)
    assert re.findall(r'LAST_EXECUTED\s+2020-09-15 00:00:00', captured_two.out)
    assert re.findall(r'GIT_URL\s+project_repo_url', captured_two.out)
    assert re.findall(r'GIT_BRANCH\s+ project_repo_branch', captured_two.out)


@patch('bodywork.cli.cronjobs.k8s')
def test_display_cronjob_workflow_history(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_cronjob_workflow_history('bodywork-dev', 'bodywork-test-project')
    captured_one = capsys.readouterr()
    assert 'namespace=bodywork-dev could not be found' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.list_workflow_jobs.return_value = {
        'workflow-job-12345': {
            'start_time': datetime(2020, 10, 19, 1, 15),
            'completion_time': datetime(2020, 10, 19, 1, 30),
            'active': False,
            'succeeded': True,
            'failed': False
        }
    }
    display_cronjob_workflow_history('bodywork-dev', 'bodywork-test-project')
    captured_two = capsys.readouterr()
    lines = captured_two.out.split('\n')
    header = lines[2]
    data = lines[3]
    assert ('JOB_NAME' in header) and ('workflow-job-12345' in data)
    assert ('START_TIME' in header) and (str(datetime(2020, 10, 19, 1, 15)) in data)
    assert ('COMPLETION_TIME' in header) and (str(datetime(2020, 10, 19, 1, 30)) in data)
    assert (('ACTIVE' in header) and ('SUCCEEDED' in header) and ('FAILED' in header)
                and (f'0{" "*19}1{" "*19}0' in data))


@patch('bodywork.cli.cronjobs.k8s')
def test_display_cronjob_workflow_job_logs(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    display_cronjob_workflow_logs('bodywork-dev', 'bodywork-test-project-12345')
    captured_one = capsys.readouterr()
    assert 'namespace=bodywork-dev could not be found' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.get_latest_pod_name.return_value = None
    display_cronjob_workflow_logs('bodywork-dev', 'bodywork-test-project-12345')
    captured_two = capsys.readouterr()
    assert 'find pod for workflow-job=bodywork-test-project-12345' in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.get_latest_pod_name.return_value = 'bodywork-test-project-12345-pqrs'
    mock_k8s_module.get_pod_logs.return_value = 'INFO - foo.py - bar'
    display_cronjob_workflow_logs('bodywork-dev', 'bodywork-test-project-12345')
    captured_three = capsys.readouterr()
    assert 'INFO - foo.py - bar' in captured_three.out
