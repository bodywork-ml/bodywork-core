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
Pytest fixtures for use with all unit and functional testing modules.
"""
import os

from typing import Iterable
from pytest import fixture


@fixture(scope="function")
def k8s_env_vars() -> Iterable[bool]:
    try:
        os.environ["KUBERNETES_SERVICE_HOST"]
    except KeyError:
        os.environ["KUBERNETES_SERVICE_HOST"] = "FOO"
    finally:
        yield True
    del os.environ["KUBERNETES_SERVICE_HOST"]



