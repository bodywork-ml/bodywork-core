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
This module contains functions for managing Kubernetes secrets. They are
targeted for use via the CLI.
"""
from typing import Dict, Iterable, Tuple

from .terminal import print_dict, print_info, print_warn
from .. import k8s


def _parse_secret_key_value_pair(kv_string: str) -> Tuple[str, str]:
    """Parse KEY=VALUE strings used in secrets.

    :param kv_string: The string containing the key-value data.
    :raises ValueError: if the string is malformed in any way.
    :return: Separated key and value.
    """
    error_msg = "secret key-value pair not in KEY=VALUE format"
    equals_sign = kv_string.find("=")
    if equals_sign == -1:
        raise ValueError(error_msg)
    key = kv_string[:equals_sign]
    if len(key) == 0:
        raise ValueError(error_msg)
    value = kv_string[(equals_sign + 1):]
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


def create_secret(
    namespace: str, group: str, secret_name: str, keys_and_values: Dict[str, str]
) -> None:
    """Create a new secret within a k8s namespace.

    :param namespace: Namespace in which to create the secret.
    :param group: The group to create the secret in.
    :param secret_name: The name to give the secret.
    :param keys_and_values: The secret keys (i.e. variable names) and
        the associated values to assign to them.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    k8s.create_secret(
        namespace,
        k8s.create_complete_secret_name(group, secret_name),
        group,
        keys_and_values,
    )
    print_info(f"Created secret={secret_name} in group={group}.")


def update_secret(
    namespace: str, group: str, secret_name: str, keys_and_values: Dict[str, str]
) -> None:
    """Update a secret within a k8s namespace.

    :param namespace: Namespace in which to look for secrets.
    :param group: The group the secret belongs to.
    :param secret_name: The name of the secret to update.
    :param keys_and_values:
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if not k8s.secret_exists(
        namespace, k8s.create_complete_secret_name(group, secret_name)
    ):
        print_warn(f"Could not find secret={secret_name} in group={group}.")
        return None
    k8s.update_secret(
        namespace, k8s.create_complete_secret_name(group, secret_name), keys_and_values
    )
    print_info(f"Updated secret={secret_name} in group={group}.")


def delete_secret(namespace: str, group: str, secret_name: str) -> None:
    """Delete a secret within a k8s namespace.

    :param namespace: Namespace in which to look for secrets.
    :param group: The group the secret belongs to.
    :param secret_name: The name of the secret to delete.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if not k8s.secret_exists(
        namespace, k8s.create_complete_secret_name(group, secret_name)
    ):
        print_warn(f"Could not find secret={secret_name} in group={group}.")
        return None
    k8s.delete_secret(namespace, k8s.create_complete_secret_name(group, secret_name))
    print_info(f"Deleted secret={secret_name} from group={group}.")


def delete_secret_group(namespace: str, group: str) -> None:
    """Delete a group of secrets within a k8s namespace.

    :param namespace: Namespace in which to look for secrets group.
    :param group: The group of secrets to delete.
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    if not k8s.secret_group_exists(namespace, group):
        print_warn(f"Could not find secret group={group}.")
        return None
    k8s.delete_secret_group(namespace, group)
    print_info(f"Deleted secret group={group}.")


def display_secrets(
    namespace: str, group: str = None, secret_name: str = None
) -> None:
    """Print secrets to stdout.

    :param namespace: Namespace in which to look for secrets.
    :param group: Group the secrets to display belong to.
    :param secret_name: Display the available keys in just the secret with
        this name, defaults to None
    """
    if not k8s.namespace_exists(namespace):
        print_warn(f"Could not find namespace={namespace} on k8s cluster.")
        return None
    secrets = k8s.list_secrets(namespace, group)
    if secret_name and not group:
        print_warn("Please specify which secrets group the secret belongs to.")
        return None
    if secret_name:
        try:
            complete_secret_name = k8s.create_complete_secret_name(
                str(group), str(secret_name)
            )
            print_dict(
                secrets[complete_secret_name].data,
                _create_table_name(str(secret_name), str(group)),
            )
        except KeyError:
            print_warn(f"Cannot find secret={secret_name}.")
    elif group:
        for secret in secrets.items():
            table_name = _create_table_name(secret[0].split(f"{group}-")[1], group)
            print_dict(secret[1].data, table_name)
    else:
        table_data = {
            secret.name.split(f"{secret.group}-")[1]: secret.group
            for _, secret in secrets.items()
            if secret.group is not None
        }
        print_dict(table_data, "all secrets", "Secret Name", "Bodywork Secret Group")


def _create_table_name(secret_name: str, group: str) -> str:
    return f"{secret_name} in group {group}"
