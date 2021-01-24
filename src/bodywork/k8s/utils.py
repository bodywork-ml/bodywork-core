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
Helper functions for working with the Kubernetes API.
"""
import json
from typing import cast

from kubernetes.client.rest import ApiException


def api_exception_msg(e: ApiException) -> str:
    """Get k8s API error message from exception object.

    :param e: Kubernetes API exception
    :return: Error message returned by the k8s API.
    """
    try:
        body = json.loads(e.body)
        message = body['message']
        return cast(str, message)
    except (KeyError, TypeError):
        return ''
