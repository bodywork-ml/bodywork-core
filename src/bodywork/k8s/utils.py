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
