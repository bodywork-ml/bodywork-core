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
This module contains functions for managing Kubernetes secrets. They are
targeted for use via the CLI.
"""
from typing import Dict, Iterable, Optional, Tuple

from .. import k8s


def _parse_secret_key_value_pair(kv_string: str) -> Tuple[str, str]:
    """Parse KEY=VALUE strings used in secrets.

    :param kv_string: The string containing the key-value data.
    :raises ValueError: if the string is malformed in any way.
    :return: Seperated key and value.
    """
    error_msg = "secret key-value pair not in KEY=VALUE format"
    equals_sign = kv_string.find("=")
    if equals_sign == -1:
        raise ValueError(error_msg)
    key = kv_string[:equals_sign]
    if len(key) == 0:
        raise ValueError(error_msg)
    value = kv_string[equals_sign + 1:]
    if len(value) == 0:
        raise ValueError(error_msg)
    return key, value


def parse_cli_secrets_strings(key_value_strings: Iterable[str]) -> Dict[str, str]:
    """Parse CLI secrets string into mapping of secret keys to values.

    :param key_value_strings: CLI secrets string.
    :return: Mapping of secret keys to values
    """
    var_names_and_values = dict(
        _parse_secret_key_value_pair(key_value_string)
        for key_value_string in key_value_strings
    )
    return var_names_and_values


def create_secret_in_namespace(
    namespace: str, secret_name: str, keys_and_values: Dict[str, str]
) -> None:
    """Create a new secret within a k8s namespace.

    :param namespace: Namespace in which to create the secret.
    :param secret_name: The name to give the secret.
    :param keys_and_values: The secret keys (i.e. variable names) and
        the associated values to assign to them.
    """
    if not k8s.namespace_exists(namespace):
        print(f"namespace={namespace} could not be found on k8s cluster")
        return None
    k8s.create_secret(namespace, secret_name, keys_and_values)
    print(f"secret={secret_name} created in namespace={namespace}")


def delete_secret_in_namespace(namespace: str, secret_name: str) -> None:
    """Delete a secret within a k8s namespace.

    :param namespace: Namespace in which to look for secrets.
    :param secret_name: The name of the secret to delete.
    """
    if not k8s.namespace_exists(namespace):
        print(f"namespace={namespace} could not be found on k8s cluster")
        return None
    if not k8s.secret_exists(namespace, secret_name):
        print(f"secret={secret_name} could not be found in namespace={namespace}")
        return None
    k8s.delete_secret(namespace, secret_name)
    print(f"secret={secret_name} deleted from namespace={namespace}")


def display_secrets_in_namespace(namespace: str, secret: Optional[str] = None) -> None:
    """Print secrets to stdout.

    :param namespace: Namespace in which to look for secrets.
    :param secret: Display the available keys in just the secret with
        this name, defaults to None
    """
    if not k8s.namespace_exists(namespace):
        print(f"namespace={namespace} could not be found on k8s cluster")
        return None
    else:
        secrets = k8s.list_secrets_in_namespace(namespace)
        if secret is not None:
            try:
                print(f"\n-- {secret}:")
                for secret_key, secret_value in secrets[secret].items():
                    print(f"-> {secret_key}={secret_value}".replace("\n", ""))
            except KeyError:
                print(f"cannot find secret={secret} in namespace={namespace}")
        else:
            for secret_name, secret_data in secrets.items():
                print(f"\n-- {secret_name}:")
                for secret_key, secret_value in secret_data.items():
                    print(f"-> {secret_key}={secret_value}".replace("\n", ""))
