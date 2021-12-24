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
from re import findall

from pytest import mark
from subprocess import run

from bodywork.k8s import replicate_secrets_in_namespace, secret_exists


@mark.usefixtures("setup_cluster")
@mark.usefixtures("add_secrets")
def test_replicate_secrets_in_namespace(test_namespace: str):
    namespace = test_namespace
    replicate_secrets_in_namespace(namespace, "testsecrets")
    assert secret_exists(namespace, "bodywork-test-project-credentials", "USERNAME")


@mark.usefixtures("setup_cluster")
@mark.usefixtures("add_secrets")
def test_update_secret():
    process_one = run(
        [
            "bodywork",
            "update",
            "secret",
            "bodywork-test-project-credentials",
            "--group=testsecrets",
            "--data",
            "PASSWORD=updated",
        ],
        encoding="utf-8",
        capture_output=True,
    )

    assert process_one.returncode == 0
    assert (
        "Updated secret=bodywork-test-project-credentials in group=testsecrets"
        in process_one.stdout
    )


@mark.usefixtures("setup_cluster")
@mark.usefixtures("add_secrets")
def test_display_all_secrets():
    process_one = run(
        [
            "bodywork",
            "get",
            "secrets",
        ],
        encoding="utf-8",
        capture_output=True,
    )

    assert process_one.returncode == 0
    assert findall(r"bodywork-test-project-credentials.+testsecret", process_one.stdout)


@mark.usefixtures("setup_cluster")
@mark.usefixtures("add_secrets")
def test_cli_secret_handler_crud():

    process_one = run(
        [
            "bodywork",
            "create",
            "secret",
            "pytest-credentials",
            "--group=test",
            "--data",
            "USERNAME=alex",
            "--data",
            "PASSWORD=alex123",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Created secret=pytest-credentials in group=test" in process_one.stdout
    assert process_one.returncode == 0

    process_two = run(
        [
            "bodywork",
            "get",
            "secret",
            "pytest-credentials",
            "--group=test",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert findall(r"USERNAME.+alex", process_two.stdout)
    assert findall(r"PASSWORD.+alex123", process_two.stdout)
    assert process_two.returncode == 0

    process_three = run(
        [
            "bodywork",
            "delete",
            "secret",
            "pytest-credentials",
            "--group=test",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Deleted secret=pytest-credentials from group=test" in process_three.stdout
    assert process_three.returncode == 0

    process_four = run(
        [
            "bodywork",
            "get",
            "secret",
            "pytest-credentials",
            "--group=test",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "" in process_four.stdout
    assert process_four.returncode == 0
