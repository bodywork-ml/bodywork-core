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
High-level interface to the Kubernetes core API as used to manage
Kubernetes namespaces for Bodywork projects.
"""
import sys
from time import sleep

from kubernetes import client as k8s

from .utils import make_valid_k8s_name


def namespace_exists(namespace: str) -> bool:
    """Does the namespace exist on the Kubernetes cluster.

    :param namespace: Kubernetes namespace to check.
    :return: True if the namespace was found, otherwise False.
    """
    namespace_objects = k8s.CoreV1Api().list_namespace().items
    namespace_names = [
        namespace_object.metadata.name for namespace_object in namespace_objects
    ]
    return True if namespace in namespace_names else False


def create_namespace(name: str) -> None:
    """Create a new namespace.

    :param name: Kubernetes namespace to create.
    """
    valid_k8s_name = make_valid_k8s_name(name)
    k8s.CoreV1Api().create_namespace(
        body=k8s.V1Namespace(metadata=k8s.V1ObjectMeta(name=valid_k8s_name))
    )


def delete_namespace(name: str, print_progress: bool = False) -> None:
    """Delete a new namespace and wait until finished.

    :param name: Kubernetes namespace to delete.
    """
    k8s.CoreV1Api().delete_namespace(name=name, propagation_policy="Background")
    if print_progress:
        while namespace_exists(name):
            sleep(1)
            print(".", end="")
            sys.stdout.flush()
        print("")
    else:
        while namespace_exists(name):
            sleep(1)
