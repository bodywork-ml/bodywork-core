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
High-level interface to the Kubernetes secrets API as used to create and
manage secrets required by Bodywork stage containers.
"""
from typing import Dict, List, Tuple
from base64 import b64decode
from dataclasses import dataclass
from pathlib import Path
from kubernetes import client as k8s

from .utils import make_valid_k8s_name
from ..constants import (
    SECRET_GROUP_LABEL,
    BODYWORK_NAMESPACE,
    SSH_PRIVATE_KEY_ENV_VAR,
    SSH_SECRET_NAME,
)


@dataclass
class Secret:
    name: str
    group: str
    data: Dict[str, str]


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

    :param namespace: Kubernetes namespace in which to look for secrets.
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
                    key=var_name,
                    name=secret_name,
                    optional=False,
                )
            ),
        )
        for secret_name, var_name in secret_varname_pairs
    ]
    return env_vars


def replicate_secrets_in_namespace(target_namespace: str, secrets_group) -> None:
    """Copy secrets in group to target namespace.

    :param target_namespace: K8s namespace to copy the secrets to.
    :param secrets_group: The group of secrets to copy.
    """

    secrets = k8s.CoreV1Api().list_namespaced_secret(
        namespace=BODYWORK_NAMESPACE,
        label_selector=f"{SECRET_GROUP_LABEL}={secrets_group}",
    )
    for secret in secrets.items:
        secret_name = secret.metadata.name.split(f"{secrets_group}-", 1)[1]
        copy = k8s.V1Secret(
            metadata=k8s.V1ObjectMeta(
                namespace=target_namespace,
                name=secret_name,
                labels={SECRET_GROUP_LABEL: secrets_group},
            ),
            data=secret.data,
        )
        if secret_exists(target_namespace, secret_name):
            k8s.CoreV1Api().replace_namespaced_secret(
                namespace=target_namespace, name=secret_name, body=copy
            )
        else:
            k8s.CoreV1Api().create_namespaced_secret(
                namespace=target_namespace, body=copy
            )


def secret_exists(
    namespace: str, secret_name: str, secret_key: str = None
) -> bool:
    """Does a secret and a key within a secret, exist.

    :param namespace: Kubernetes namespace in which to look for secrets.
    :param secret_name: The name of the k8s secret to look for.
    :param secret_key: The variable key within the secret to look for.
    :return: True if the secret was found and the key within the secret
        was also found, otherwise False.
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


def secret_group_exists(namespace: str, group: str) -> bool:
    """Does the specified secret group exist.

    :param namespace: Kubernetes namespace in which to look for secrets group.
    :param group: Name of secrets group.
    :return: True if group exists, otherwise False.
    """
    items = (
        k8s.CoreV1Api()
        .list_namespaced_secret(
            namespace=namespace, label_selector=f"{SECRET_GROUP_LABEL}={group}"
        )
        .items
    )
    return len(items) > 0


def create_secret(
    namespace: str, name: str, group: str, keys_and_values: Dict[str, str]
) -> None:
    """Create a new secret with multiple key-value pairs.

    :param namespace: Namespace to deploy the secret to.
    :param name: The name to give the secret - e.g. 'aws-credentials'.
    :param group: The group to create the secret in.
    :param keys_and_values: Mapping of secret keys (or variable names)
        and their values.
    """
    secret = k8s.V1Secret(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=make_valid_k8s_name(name),
            labels={SECRET_GROUP_LABEL: group},
        ),
        string_data=keys_and_values,
    )
    k8s.CoreV1Api().create_namespaced_secret(namespace=namespace, body=secret)


def update_secret(namespace: str, name: str, keys_and_values: Dict[str, str]) -> None:
    """Update an existing secret.

    :param namespace: Namespace the secret is in.
    :param name: The name of the secret'.
    :param keys_and_values: Mapping of secret keys (or variable names)
        and their values.
    """
    secret = k8s.V1Secret(
        metadata=k8s.V1ObjectMeta(
            namespace=namespace,
            name=make_valid_k8s_name(name),
        ),
        string_data=keys_and_values,
    )
    k8s.CoreV1Api().patch_namespaced_secret(name, namespace, secret)


def delete_secret(namespace: str, name: str) -> None:
    """Delete a secret from within a namespace.

    :param namespace: Namespace in which to look for the secret to delete.
    :param name: The name of the secret to be deleted.
    """
    k8s.CoreV1Api().delete_namespaced_secret(namespace=namespace, name=name)


def delete_secret_group(namespace: str, group: str) -> None:
    """Delete a group of secrets in a namespace.

    :param namespace: Namespace in which to look for the secret to delete.
    :param group: The name of the secrets group to be deleted.
    """
    k8s.CoreV1Api().delete_collection_namespaced_secret(
        namespace=namespace, label_selector=f"{SECRET_GROUP_LABEL}={group}"
    )


def list_secrets(namespace: str, group: str = None) -> Dict[str, Secret]:
    """Get all secrets and their (decoded) data.

    :param namespace: Namespace in which to list secrets.
    :param group: Group of secrets to list.
    """
    if group is None:
        result = k8s.CoreV1Api().list_namespaced_secret(namespace=namespace)
    else:
        result = k8s.CoreV1Api().list_namespaced_secret(
            namespace=namespace,
            label_selector=f"{SECRET_GROUP_LABEL}={group}",
        )
    return {
        s.metadata.name: Secret(
            s.metadata.name,
            s.metadata.labels[SECRET_GROUP_LABEL]
            if s.metadata.labels and SECRET_GROUP_LABEL in s.metadata.labels
            else None,
            s.string_data
            if s.string_data
            else {
                key: b64decode(value).decode("utf-8") for (key, value) in s.data.items()
            },
        )
        for s in result.items
    }


def create_ssh_key_secret_from_file(group: str, ssh_key_path: Path) -> None:
    """Creates/updates SSH key secret with the key from the specified file.

    :param group: Secrets group to create the key in.
    :param ssh_key_path: The filepath to the SSH key file.
    """
    if not ssh_key_path.exists():
        raise FileNotFoundError(f"Could not find SSH key file at: {ssh_key_path}")
    with ssh_key_path.open() as file_handle:
        data = {SSH_PRIVATE_KEY_ENV_VAR: file_handle.read()}
    secret_name = create_complete_secret_name(group, SSH_SECRET_NAME)
    if secret_exists(BODYWORK_NAMESPACE, secret_name):
        update_secret(BODYWORK_NAMESPACE, secret_name, data)
    else:
        create_secret(
            BODYWORK_NAMESPACE,
            secret_name,
            group,
            data,
        )


def create_secret_env_variable(group: str = None) -> k8s.V1EnvVar:
    """Create SSH environment variable from SSH secret

    :param group: Link to secret in group.
    :return: K8s SSH environment variable.
    """
    if group:
        name = f"{group}-{SSH_SECRET_NAME}"
    else:
        name = SSH_SECRET_NAME
    return k8s.V1EnvVar(
        name=SSH_PRIVATE_KEY_ENV_VAR,
        value_from=k8s.V1EnvVarSource(
            secret_key_ref=k8s.V1SecretKeySelector(
                key=SSH_PRIVATE_KEY_ENV_VAR, name=name, optional=False
            )
        ),
    )


def create_complete_secret_name(group: str, name: str) -> str:
    return f"{group}-{name}"
