"""
Tests for all code that handles printing and logging to stdout.
"""
from re import findall

from _pytest.capture import CaptureFixture

from bodywork.cli.terminal import print_dict, print_info, print_pod_logs, print_warn


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
    assert findall(r"─.+logs for stage = foo.+─", stdout)
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
