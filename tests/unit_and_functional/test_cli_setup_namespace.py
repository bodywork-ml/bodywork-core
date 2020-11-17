"""
Test high-level namespace, service account and roles setup.
"""
from unittest.mock import MagicMock, patch

from _pytest.capture import CaptureFixture

from bodywork.constants import (
    BODYWORK_WORKFLOW_CLUSTER_ROLE,
    BODYWORK_WORKFLOW_SERVICE_ACCOUNT,
    BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT
)
from bodywork.cli.setup_namespace import (
    is_namespace_available_for_bodywork,
    setup_namespace_with_service_accounts_and_roles
)


@patch('bodywork.cli.setup_namespace.k8s')
def test_is_namespace_setup_for_bodywork(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    SA1 = BODYWORK_WORKFLOW_SERVICE_ACCOUNT
    CRB = BODYWORK_WORKFLOW_CLUSTER_ROLE
    SA2 = BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT

    mock_k8s_module.namespace_exists.return_value = False
    namespace_setup = is_namespace_available_for_bodywork('bodywork-dev')
    capture_one = capsys.readouterr()
    assert namespace_setup is False
    assert 'namespace=bodywork-dev does not exist' in capture_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.service_account_exists.side_effect = [True, True]
    mock_k8s_module.cluster_role_binding_exists.return_value = True
    namespace_setup = is_namespace_available_for_bodywork('bodywork-dev')
    capture_two = capsys.readouterr()
    assert namespace_setup is True
    assert 'namespace=bodywork-dev is setup for use by Bodywork' in capture_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.service_account_exists.side_effect = [False, False]
    mock_k8s_module.cluster_role_binding_exists.return_value = False
    mock_k8s_module.workflow_cluster_role_binding_name.return_value = (
        f'{CRB}--bodywork-dev'
    )
    namespace_setup = is_namespace_available_for_bodywork('bodywork-dev')
    capture_three = capsys.readouterr()
    assert namespace_setup is False
    assert f'service-account={SA1} is missing from namespace' in capture_three.out
    assert f'cluster-role-binding={CRB}--bodywork-dev is missing' in capture_three.out
    assert f'service-account={SA2} is missing from namespace' in capture_three.out


@patch('bodywork.cli.setup_namespace.k8s')
def test_setup_namespace_on_k8s_cluster(
    mock_k8s_module: MagicMock,
    capsys: CaptureFixture
):
    SA1 = BODYWORK_WORKFLOW_SERVICE_ACCOUNT
    SA2 = BODYWORK_JOBS_DEPLOYMENTS_SERVICE_ACCOUNT

    mock_k8s_module.namespace_exists.return_value = False
    mock_k8s_module.create_namespace.side_effect = None
    mock_k8s_module.service_account_exists.side_effect = [False, True]
    mock_k8s_module.setup_workflow_service_account.side_effect = None
    setup_namespace_with_service_accounts_and_roles('the-namespace')
    captured_one = capsys.readouterr()
    assert 'creating namespace=the-namespace' in captured_one.out
    assert f'creating service-account={SA1}' in captured_one.out
    assert f'service-account={SA2} already exists in namespace' in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.create_namespace.side_effect = None
    mock_k8s_module.service_account_exists.side_effect = [True, True]
    mock_k8s_module.setup_workflow_service_account.side_effect = None
    setup_namespace_with_service_accounts_and_roles('the-namespace')
    captured_two = capsys.readouterr()
    assert 'namespace=the-namespace already exists' in captured_two.out
    assert f'service-account={SA1} already exists in namespace' in captured_two.out
    assert f'service-account={SA2} already exists in namespace' in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.create_namespace.side_effect = None
    mock_k8s_module.service_account_exists.side_effect = [False, False]
    mock_k8s_module.setup_workflow_service_account.side_effect = None
    mock_k8s_module.setup_job_and_deployment_service_accounts.side_effect = None
    setup_namespace_with_service_accounts_and_roles('the-namespace')
    captured_three = capsys.readouterr()
    assert 'namespace=the-namespace already exists' in captured_three.out
    assert f'creating service-account={SA1}' in captured_three.out
    assert f'creating service-account={SA2}' in captured_three.out
