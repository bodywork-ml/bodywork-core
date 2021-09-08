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
Integration testing secrets functionality with k8s.
"""

from pytest import mark
from subprocess import CalledProcessError, run

from bodywork.k8s import replicate_secrets_in_namespace, secret_exists


@mark.usefixtures("add_secrets")
@mark.usefixtures("setup_cluster")
def test_replicate_secrets_in_namespace():
    namespace = "bodywork-dev"

    replicate_secrets_in_namespace(namespace, "testsecrets")

    assert secret_exists(namespace, "bodywork-test-project-credentials", "USERNAME")


@mark.usefixtures("add_secrets")
@mark.usefixtures("setup_cluster")
def test_update_secret():
    process_one = run(
        [
            "bodywork",
            "secret",
            "update",
            "--group=testsecrets",
            "--name=bodywork-test-project-credentials",
            "--data",
            "PASSWORD=updated",
        ],
        encoding="utf-8",
        capture_output=True,
    )

    assert process_one.returncode == 0
    assert "secret=bodywork-test-project-credentials in group=testsecrets updated" in process_one.stdout


@mark.usefixtures("add_secrets")
@mark.usefixtures("setup_cluster")
def test_display_all_secrets():
    process_one = run(
        [
            "bodywork",
            "secret",
            "display",
        ],
        encoding="utf-8",
        capture_output=True,
    )

    assert process_one.returncode == 0
    assert "testsecrets-bodywork-test-project-credentials" in process_one.stdout


@mark.usefixtures("setup_cluster")
def test_cli_secret_handler_crud(test_namespace: str):

    process_one = run(
        [
            "bodywork",
            "secret",
            "create",
            "--group=test",
            "--name=pytest-credentials",
            "--data",
            "USERNAME=alex",
            "PASSWORD=alex123",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "secret=pytest-credentials created in group=test" in process_one.stdout
    assert process_one.returncode == 0

    process_two = run(
        [
            "bodywork",
            "secret",
            "display",
            "--name=pytest-credentials",
            "--group=test",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "USERNAME=alex" in process_two.stdout
    assert "PASSWORD=alex123" in process_two.stdout
    assert process_two.returncode == 0

    process_three = run(
        [
            "bodywork",
            "secret",
            "delete",
            "--group=test",
            "--name=pytest-credentials",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "secret=pytest-credentials in group=test deleted" in process_three.stdout
    assert process_three.returncode == 0

    process_four = run(
        [
            "bodywork",
            "secret",
            "display",
            "--group=test",
            "--name=pytest-credentials",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "" in process_four.stdout
    assert process_four.returncode == 0
