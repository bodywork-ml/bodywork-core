# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020  Bodywork Machine Learning Ltd.

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
