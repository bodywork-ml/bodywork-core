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
import re
from typing import cast, List, Tuple

from kubernetes.client.rest import ApiException
from kubernetes import client as k8s


EnvVars = List[k8s.V1EnvVar]


def api_exception_msg(e: ApiException) -> str:
    """Get k8s API error message from exception object.

    :param e: Kubernetes API exception
    :return: Error message returned by the k8s API.
    """
    try:
        body = json.loads(e.body)
        message = body["message"]
        return cast(str, message)
    except (KeyError, TypeError):
        return ""


def make_valid_k8s_name(name: str) -> str:
    """Remove invalid characters from k8s resource name.

    :param name: Original intended name.
    :return: Valid Kubernetes resource name.
    """
    return re.sub(r"(\s|_)", "-", name.strip())


def create_k8s_environment_variables(
    key_value_pairs: List[Tuple[str, str]]
) -> List[k8s.V1EnvVar]:
    """Creates K8s environment variable from key/value pairs.

    :param key_value_pairs: Environment variables to create.
    :return: List of K8s environment variables.
    """
    return [k8s.V1EnvVar(name=name, value=value) for name, value in key_value_pairs]
