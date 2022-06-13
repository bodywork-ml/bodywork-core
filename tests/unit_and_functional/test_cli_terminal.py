"""
Tests for all code that handles printing and logging to stdout.
"""
from datetime import datetime
from re import findall
from turtle import up
from unittest.mock import patch, MagicMock

from _pytest.capture import CaptureFixture

from bodywork.cli.terminal import (
    _get_progress_description,
    make_progress_bar,
    print_dict,
    print_info,
    print_pod_logs,
    print_warn,
    update_progress_bar,
)


def test_print_dict_renders_dicts(capsys: CaptureFixture):
    data = {"name": "Alex Ioannides", "age": 39}
    print_dict(data, "data", "ColA", "ColB")
    stdout = capsys.readouterr().out
    assert findall(r"ColA.+|.+ColB", stdout)
    assert findall(r"name.+|.+Alex Ioannides", stdout)
    assert findall(r"age.+|.+39", stdout)


def test_print_pod_logs_renders_logs(capsys: CaptureFixture):
    logs = (
        "[09/13/21 15:02:05] INFO     Something happened"
        "[09/13/21 15:02:05] INFO     Something else happened"
    )
    print_pod_logs(logs, "foo")
    stdout = capsys.readouterr().out
    assert findall(r"─.+foo.+─", stdout)
    assert "[09/13/21 15:02:05] INFO     Something happened" in stdout
    assert "[09/13/21 15:02:05] INFO     Something else happened" in stdout


def test_print_info_and_warn_print_to_stdout_with_different_styles(
    capsys: CaptureFixture,
):
    print_info("foo")
    captured_stdout_one = capsys.readouterr().out
    assert "foo" in captured_stdout_one

    print_warn("foo")
    captured_stdout_two = capsys.readouterr().out
    assert "foo" in captured_stdout_two


def test_make_progress_bar():
    progress_bar = make_progress_bar(10, 1)
    assert len(progress_bar.task_ids) == 1
    assert progress_bar.tasks[0].remaining == 10 / 1
    assert progress_bar.tasks[0].total == 10 / 1


@patch("bodywork.cli.terminal.datetime")
def test_get_progress_description(mock_dt: MagicMock):
    mock_dt.now.return_value = datetime(2022, 1, 1)
    description = _get_progress_description()
    assert "[01/01/22 00:00:00]" in description


@patch("bodywork.cli.terminal.Progress")
@patch("bodywork.cli.terminal._get_progress_description")
def test_get_progress_description(
    mock_get_progress_desc: MagicMock, mock_progress: MagicMock
):
    mock_progress.task_ids = ["foo"]
    mock_get_progress_desc.return_value = "bar"
    update_progress_bar(mock_progress)
    mock_progress.update.assert_called_once_with("foo", advance=1, description="bar")
