# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020-2022  Bodywork Machine Learning Ltd.

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
Test high-level namespace, service account and roles setup.
"""
from unittest.mock import MagicMock, patch

from _pytest.capture import CaptureFixture

from bodywork.constants import (
    BODYWORK_WORKFLOW_CLUSTER_ROLE,
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
)
from bodywork.cli.setup_namespace import (
    is_namespace_available_for_bodywork,
    setup_namespace_with_service_accounts_and_roles,
)


@patch("bodywork.cli.setup_namespace.k8s")
def test_is_namespace_setup_for_bodywork(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    SA1 = BODYWORK_WORKFLOW_SERVICE_ACCOUNT
    CRB = BODYWORK_WORKFLOW_CLUSTER_ROLE

    mock_k8s_module.namespace_exists.return_value = False
    namespace_setup = is_namespace_available_for_bodywork("bodywork-dev")
    capture_one = capsys.readouterr()
    assert namespace_setup is False
    assert "Could not find namespace=bodywork-dev on k8s cluster" in capture_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.service_account_exists.side_effect = [False, False]
    mock_k8s_module.cluster_role_binding_exists.return_value = False
    mock_k8s_module.workflow_cluster_role_binding_name.return_value = (
        f"{CRB}--bodywork-dev"
    )
    namespace_setup = is_namespace_available_for_bodywork("bodywork-dev")
    capture_two = capsys.readouterr()
    assert namespace_setup is False
    assert f"Missing service-account={SA1}" in capture_two.out
    assert f"Missing cluster-role-binding={CRB}--bodywork-dev" in capture_two.out


@patch("bodywork.cli.setup_namespace.k8s")
def test_setup_namespace_on_k8s_cluster(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    SA1 = BODYWORK_WORKFLOW_SERVICE_ACCOUNT

    mock_k8s_module.namespace_exists.return_value = False
    mock_k8s_module.create_namespace.side_effect = None
    mock_k8s_module.service_account_exists.side_effect = [False, True]
    mock_k8s_module.setup_workflow_service_account.side_effect = None
    setup_namespace_with_service_accounts_and_roles("the-namespace")
    captured_one = capsys.readouterr()
    assert "Creating namespace=the-namespace" in captured_one.out
    assert f"Creating service-account={SA1}" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.create_namespace.side_effect = None
    mock_k8s_module.service_account_exists.side_effect = [True, True]
    mock_k8s_module.setup_workflow_service_account.side_effect = None
    setup_namespace_with_service_accounts_and_roles("the-namespace")
    captured_two = capsys.readouterr()
    assert "namespace=the-namespace already exists" in captured_two.out
    assert f"service-account={SA1} already exists" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.create_namespace.side_effect = None
    mock_k8s_module.service_account_exists.side_effect = [False, False]
    mock_k8s_module.setup_workflow_service_account.side_effect = None
    mock_k8s_module.setup_job_and_deployment_service_accounts.side_effect = None
    setup_namespace_with_service_accounts_and_roles("the-namespace")
    captured_three = capsys.readouterr()
    assert "namespace=the-namespace already exists" in captured_three.out
    assert f"Creating service-account={SA1}" in captured_three.out
