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
High-level interface to the Kubernetes secrets API as used to create and
manage secrets required by Bodywork stage containers.
"""
from base64 import b64decode
from typing import Dict, List, Optional, Tuple

from kubernetes import client as k8s

from .utils import make_valid_k8s_name


def configure_env_vars_from_secrets(
    namespace: str, secret_varname_pairs: List[Tuple[str, str]]
) -> List[k8s.V1EnvVar]:
    """Configure container environment variables from secrets.

    Enables secret values to be mounted as environment variables in a
    Bodywork stage-runner container. For example, with a secret created
    using kubectl as follows,

        kubectl -n bodywork-dev create secret generic foobar \
            --from-literal=FOO=bar \
            --from-literal=BAR=foo

    This function can be used to configure the environment variables FOO
    and BAR for any batch job or service deployment.

    :param namespece: Kubernetes namespace in which to look for secrets.
    :param secret_varname_pairs: List of secret, variable-name pairs.
    :raises RuntimeError: if any of the secrets or their keys cannot be
        found.
    :return: A configured list of environment variables.
    """
    missing_secrets_info = [
        f"cannot find key={var_name} in secret={secret_name} in namespace={namespace}"
        for secret_name, var_name in secret_varname_pairs
        if not secret_exists(namespace, secret_name, var_name)
    ]
    if missing_secrets_info:
        msg = "; ".join(missing_secrets_info)
        raise RuntimeError(msg)

    env_vars = [
        k8s.V1EnvVar(
            name=var_name,
            value_from=k8s.V1EnvVarSource(
                secret_key_ref=k8s.V1SecretKeySelector(
                    key=var_name, name=secret_name, optional=False
                )
            ),
        )
        for secret_name, var_name in secret_varname_pairs
    ]
    return env_vars


def secret_exists(
    namespace: str, secret_name: str, secret_key: Optional[str] = None
) -> bool:
    """Does a secret and a key within a secret, exist.

    :param namespece: Kubernetes namespace in which to look for secrets.
    :param secret_name: The name of the k8s secret to look for.
    :param secret_key: The variable key within the secret to look for.
    :return: True if the secret was found and the key within the secret
        was also found, othewise False.
    """
    existing_secrets = k8s.CoreV1Api().list_namespaced_secret(namespace=namespace)
    secret_data = [
        secret.data
        for secret in existing_secrets.items
        if secret.metadata.name == secret_name
    ]
    if len(secret_data) == 1 and secret_key is None:
        return True
    elif len(secret_data) == 1 and secret_key is not None:
        return True if secret_data[0].get(secret_key) is not None else False
    else:
        return False


def create_secret(namespace: str, name: str, keys_and_values: Dict[str, str]) -> None:
    """Create a new secret with multiple key-value pairs.

    :param namespace: Namespace to deploy the secret to.
    :param name: The name to give the secret - e.g. 'aws-credentials'.
    :param keys_and_values: Mapping of secret keys (or variable names)
        and their values.
    """
    secret = k8s.V1Secret(
        metadata=k8s.V1ObjectMeta(namespace=namespace, name=make_valid_k8s_name(name)),
        string_data=keys_and_values,
    )
    k8s.CoreV1Api().create_namespaced_secret(namespace=namespace, body=secret)


def delete_secret(namespace: str, name: str) -> None:
    """Delete a secret from within a namespace.

    :param namespace: Namespace in which to look for the secret to
        delete.
    :param name: The name of the secret to be deleted.
    """
    k8s.CoreV1Api().delete_namespaced_secret(namespace=namespace, name=name)


def list_secrets_in_namespace(namespace: str) -> Dict[str, Dict[str, str]]:
    """Get all secrets and their (decoded) data.

    :param namespace: Namespace in which to list secrets.
    """
    secrets = k8s.CoreV1Api().list_namespaced_secret(
        namespace=namespace,
    )
    secret_data_base64 = {
        s.metadata.name: s.string_data if s.string_data else s.data
        for s in secrets.items
    }
    secret_data_decoded = {
        secret_name: {
            key: b64decode(value).decode("utf-8") for key, value in secret_data.items()
        }
        for secret_name, secret_data in secret_data_base64.items()
    }
    return secret_data_decoded
