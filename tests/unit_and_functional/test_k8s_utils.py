"""
Unit tests for k8s API helper functions.
"""
from unittest.mock import Mock

from bodywork.k8s.utils import api_exception_msg


def test_api_exception_msg_retreives_message_str():
    mock_api_exception = Mock()

    mock_api_exception.body = '{"message": "foo"}'
    assert 'foo' in api_exception_msg(mock_api_exception)

    mock_api_exception.body = '{"bar": "foo"}'
    assert api_exception_msg(mock_api_exception) == ''
