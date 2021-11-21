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
Test high-level secret management functions.
"""
from re import findall
from unittest.mock import MagicMock, patch

from pytest import raises
from _pytest.capture import CaptureFixture

from bodywork.k8s.secrets import Secret
from bodywork.cli.secrets import (
    create_secret,
    delete_secret,
    display_secrets,
    parse_cli_secrets_strings,
    update_secret,
)


def test_parse_cli_secrets_strings_parses_valid_inputs():
    input_1 = ["KEY1=value1"]
    assert parse_cli_secrets_strings(input_1) == {"KEY1": "value1"}

    input_2 = ["KEY1=value1", "KEY2=value2"]
    assert parse_cli_secrets_strings(input_2) == {"KEY1": "value1", "KEY2": "value2"}


def test_parse_cli_secrets_strings_raises_exception_invalid_inputs():
    input_1 = ["KEY1value1"]
    with raises(ValueError, match="secret key-value pair not in KEY=VALUE format"):
        parse_cli_secrets_strings(input_1)

    input_2 = ["=value1"]
    with raises(ValueError, match="secret key-value pair not in KEY=VALUE format"):
        parse_cli_secrets_strings(input_2)

    input_3 = ["KEY1="]
    with raises(ValueError, match="secret key-value pair not in KEY=VALUE format"):
        parse_cli_secrets_strings(input_3)

    input_4 = [""]
    with raises(ValueError, match="secret key-value pair not in KEY=VALUE format"):
        parse_cli_secrets_strings(input_4)


@patch("bodywork.cli.secrets.k8s")
def test_create_secrets_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    create_secret("bodywork-dev", "xyz", "test-credentials", {"A": "b"})
    captured_one = capsys.readouterr()
    assert "Could not find namespace=bodywork-dev on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.create_secret.side_effect = None
    create_secret("bodywork-dev", "xyz", "test-credentials", {"A": "b"})
    captured_two = capsys.readouterr()
    assert "Created secret=test-credentials in group=xyz" in captured_two.out


@patch("bodywork.cli.secrets.k8s")
def test_can_update_secret(mock_k8s_module: MagicMock, capsys: CaptureFixture):
    update_secret("bodywork-dev", "xyz", "test-credentials", {"A": "b"})
    captured_one = capsys.readouterr()

    assert "Updated secret=test-credentials in group=xyz" in captured_one.out


@patch("bodywork.cli.secrets.k8s")
def test_update_secret_prints_message_secret_does_not_exist(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.secret_exists.return_value = False

    update_secret("bodywork-dev", "xyz", "test-credentials", {"A": "b"})

    captured_one = capsys.readouterr()
    assert "Could not find secret=test-credentials in group=xyz" in captured_one.out


@patch("bodywork.cli.secrets.k8s")
def test_delete_secrets_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    delete_secret("the-namespace", "xyz", "test-credentials")
    captured_one = capsys.readouterr()
    assert "Could not find namespace=the-namespace" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.secret_exists.return_value = False
    delete_secret("the-namespace", "xyz", "test-credentials")
    captured_two = capsys.readouterr()
    assert "Could not find secret=test-credentials" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.secret_exists.return_value = True
    mock_k8s_module.delete_secret.side_effect = None
    delete_secret("the-namespace", "xyz", "test-credentials")
    captured_three = capsys.readouterr()
    assert "Deleted secret=test-credentials from group=xyz" in captured_three.out


@patch("bodywork.cli.secrets.k8s.namespace_exists")
@patch("bodywork.cli.secrets.k8s.list_secrets")
def test_display_secrets(mock_list_secrets: MagicMock, mock_namespace: MagicMock, capsys: CaptureFixture):
    mock_list_secrets.return_value = {
        "PROD-test-credentials": Secret(
            "PROD-test-credentials", "PROD", {"USERNAME": "alex", "PASSWORD": "alex123"}
        ),
        "DEV-more-test-credentials": Secret(
            "DEV-more-test-credentials", "DEV", {"FOO": "bar"}
        ),
    }

    mock_namespace.return_value = False
    display_secrets("the-namespace", secret_name="test-credentials")
    captured_one = capsys.readouterr()
    assert "Could not find namespace=the-namespace on k8s cluster" in captured_one.out

    mock_namespace.return_value = True
    display_secrets("the-namespace", secret_name="test-credentials", group="PROD")
    captured_two = capsys.readouterr()
    assert findall(".*USERNAME.+alex", captured_two.out)
    assert findall(".*PASSWORD.+alex123", captured_two.out)

    mock_namespace.return_value = True
    display_secrets("the-namespace", secret_name="test-credentialz", group="DEV")
    captured_three = capsys.readouterr()
    assert "Cannot find secret=test-credentialz" in captured_three.out

    mock_namespace.return_value = True
    display_secrets("the-namespace", None)
    captured_four = capsys.readouterr()
    assert findall(".*test-credentials.+PROD", captured_four.out)
    assert findall(".*more-test-credentials.+DEV", captured_four.out)
