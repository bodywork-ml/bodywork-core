"""
Unit tests for the high-level Kubernetes secrets interface, used to
manage secrets required by Bodywork project stages.
"""
from unittest.mock import MagicMock, patch

import kubernetes
from pytest import raises

from bodywork.k8s.secrets import (
    configure_env_vars_from_secrets,
    create_secret,
    delete_secret,
    list_secrets_in_namespace,
    secret_exists
)


@patch('bodywork.k8s.secrets.secret_exists')
def test_configure_environment_variables_raises_errors_if_secrets_cannot_be_found(
    mock_bodywork_k8s_secret_exists: MagicMock
):
    mock_bodywork_k8s_secret_exists.side_effect = [False, True]

    secrets = [
        ('aws-credentials', 'AWS_SECRET_ACCESS_KEY'),
        ('aws-credentials', 'AWS_ACCESS_KEY_ID')
    ]
    with raises(RuntimeError, match='cannot find key='):
        configure_env_vars_from_secrets('bodywork-dev', secrets)


@patch('bodywork.k8s.secrets.secret_exists')
def test_configure_env_vars_from_secrets(
    mock_bodywork_k8s_secret_exists: MagicMock
):
    mock_bodywork_k8s_secret_exists.side_effect = [True, True]

    secrets = [
        ('aws-credentials', 'AWS_SECRET_ACCESS_KEY'),
        ('aws-credentials', 'AWS_ACCESS_KEY_ID')
    ]
    env_vars = configure_env_vars_from_secrets('bodywork-dev', secrets)
    assert len(env_vars) == 2
    assert env_vars[0].name == 'AWS_SECRET_ACCESS_KEY'
    assert env_vars[0].value_from.secret_key_ref.name == 'aws-credentials'
    assert env_vars[0].value_from.secret_key_ref.key == 'AWS_SECRET_ACCESS_KEY'
    assert env_vars[1].name == 'AWS_ACCESS_KEY_ID'
    assert env_vars[1].value_from.secret_key_ref.name == 'aws-credentials'
    assert env_vars[1].value_from.secret_key_ref.key == 'AWS_ACCESS_KEY_ID'


@patch('kubernetes.client.CoreV1Api')
def test_secret_exists_identifies_existing_namespaces(
    mock_k8s_core_api: MagicMock
):
    mock_k8s_core_api().list_namespaced_secret.return_value = (
        kubernetes.client.V1SecretList(
            items=[
                kubernetes.client.V1Secret(
                    metadata=kubernetes.client.V1ObjectMeta(name='aws-credentials'),
                    data={'FOO': 'bar'}
                )
            ]
        )
    )
    assert secret_exists('bodywork-dev', 'aws-credentials', 'FOO') is True
    assert secret_exists('bodywork-dev', 'aws-credentials', 'BAR') is False
    assert secret_exists('bodywork-dev', 'aws-access-kays', 'FOO') is False


@patch('kubernetes.client.CoreV1Api')
def test_create_secret_tries_to_create_secret_with_k8s_api(
    mock_k8s_core_api: MagicMock
):
    create_secret('bodywork-dev', 'pytest-secret', {'KEY': 'value'})
    mock_k8s_core_api().create_namespaced_secret.assert_called_once_with(
        namespace='bodywork-dev',
        body=kubernetes.client.V1Secret(
            metadata=kubernetes.client.V1ObjectMeta(
                namespace='bodywork-dev',
                name='pytest-secret'
            ),
            string_data={'KEY': 'value'}
        )
    )


@patch('kubernetes.client.CoreV1Api')
def test_delete_secret_tries_to_delete_secret_with_k8s_api(
    mock_k8s_core_api: MagicMock
):
    delete_secret('bodywork-dev', 'pytest-secret')
    mock_k8s_core_api().delete_namespaced_secret.assert_called_once_with(
        namespace='bodywork-dev',
        name='pytest-secret'
    )


@patch('kubernetes.client.CoreV1Api')
def test_list_secrets_in_namespace_returns_decoded_secret_data(
    mock_k8s_core_api: MagicMock
):
    mock_k8s_core_api().list_namespaced_secret.return_value = (
        kubernetes.client.V1SecretList(
            items=[
                kubernetes.client.V1Secret(
                    metadata=kubernetes.client.V1ObjectMeta(
                        namespace='bodywork-dev',
                        name='pytest-secret'
                    ),
                    string_data={'ALEX': b'aW9hbm5pZGVz'}
                )
            ]
        )
    )
    secrets = list_secrets_in_namespace('bodywork-dev')
    assert len(secrets) == 1
    assert secrets['pytest-secret']['ALEX'] == 'ioannides'
