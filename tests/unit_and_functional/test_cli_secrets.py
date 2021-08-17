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
from unittest.mock import MagicMock, patch

from pytest import raises
from _pytest.capture import CaptureFixture

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
    assert (
        "namespace=bodywork-dev could not be found on k8s cluster" in captured_one.out
    )

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.create_secret.side_effect = None
    create_secret("bodywork-dev", "xyz", "test-credentials", {"A": "b"})
    captured_two = capsys.readouterr()
    assert "test-credentials created in group=xyz" in captured_two.out


@patch("bodywork.cli.secrets.k8s")
def test_can_update_secret(mock_k8s_module: MagicMock, capsys: CaptureFixture):
    update_secret("bodywork-dev", "xyz", "test-credentials", {"A": "b"})
    captured_one = capsys.readouterr()

    assert "secret=test-credentials in group=xyz updated" in captured_one.out


@patch("bodywork.cli.secrets.k8s")
def test_update_secret_prints_message_secret_does_not_exist(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.secret_exists.return_value = False

    update_secret("bodywork-dev", "xyz", "test-credentials", {"A": "b"})

    captured_one = capsys.readouterr()
    assert "secret=test-credentials could not be found in group=xyz" in captured_one.out


@patch("bodywork.cli.secrets.k8s")
def test_delete_secrets_in_namespace(
    mock_k8s_module: MagicMock, capsys: CaptureFixture
):
    mock_k8s_module.namespace_exists.return_value = False
    delete_secret("the-namespace", "xyz", "test-credentials")
    captured_one = capsys.readouterr()
    assert "namespace=the-namespace could not be found" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.secret_exists.return_value = False
    delete_secret("the-namespace", "xyz", "test-credentials")
    captured_two = capsys.readouterr()
    assert "secret=test-credentials could not be found" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    mock_k8s_module.secret_exists.return_value = True
    mock_k8s_module.delete_secret.side_effect = None
    delete_secret("the-namespace", "xyz", "test-credentials")
    captured_three = capsys.readouterr()
    assert (
        "test-credentials in group=xyz deleted from namespace=the-namespace"
        in captured_three.out
    )


@patch("bodywork.cli.secrets.k8s")
def test_display_secrets(mock_k8s_module: MagicMock, capsys: CaptureFixture):
    mock_k8s_module.list_secrets.return_value = {
        "PROD-test-credentials": {"USERNAME": "alex", "PASSWORD": "alex123"},
        "DEV-more-test-credentials": {"FOO": "bar"},
    }

    mock_k8s_module.namespace_exists.return_value = False
    display_secrets("the-namespace", secret="test-credentials")
    captured_one = capsys.readouterr()
    assert "could not be found on k8s cluster" in captured_one.out

    mock_k8s_module.namespace_exists.return_value = True
    display_secrets("the-namespace", secret="test-credentials", group="PROD")
    captured_two = capsys.readouterr()
    assert "USERNAME=alex" in captured_two.out
    assert "PASSWORD=alex123" in captured_two.out

    mock_k8s_module.namespace_exists.return_value = True
    display_secrets("the-namespace", secret="test-credentialz", group="DEV")
    captured_three = capsys.readouterr()
    assert "cannot find secret=test-credentialz" in captured_three.out

    mock_k8s_module.namespace_exists.return_value = True
    display_secrets("the-namespace", None)
    captured_four = capsys.readouterr()
    assert "test-credentials" in captured_four.out
    assert "USERNAME=alex" in captured_four.out
    assert "PASSWORD=alex123" in captured_four.out
    assert "more-test-credentials" in captured_four.out
    assert "FOO=bar" in captured_four.out
