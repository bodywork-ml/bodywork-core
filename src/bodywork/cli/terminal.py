from datetime import datetime
from typing import Any, Dict

from rich.console import Console
from rich.table import Table
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from ..constants import DEFAULT_K8S_POLLING_FREQ, LOG_TIME_FORMAT

console = Console(highlight=False, soft_wrap=False, width=175)


def print_info(msg: str) -> None:
    """Print an info message."""
    console.print(msg, style="green")


def print_warn(msg: str) -> None:
    """Print a warning message."""
    console.print(msg, style="red")


def print_dict(
    the_dict: Dict[str, Any],
    table_name: str = None,
    key_col_name: str = "Field",
    val_col_name: str = "Value",
) -> None:
    """Render dict as a table in terminal.

    :param the_dict: The dictionary to render.
    :param table_name: Table name, defaults to None.
    :param key_col_name: Header for the keys column, defaults to 'Field'.
    :param val_col_name: Header for the values column, defaults to 'Value'.
    """
    table = Table(title=f"{table_name if table_name else ''}", title_style="bold")
    table.add_column(f"[yellow]{key_col_name}[/yellow]", style="bold purple")
    table.add_column(f"[yellow]{val_col_name}[/yellow]", style="bold green")
    for field, value in the_dict.items():
        table.add_row(str(field), str(value))
    console.print(table)


def print_pod_logs(logs: str, header: str) -> None:
    """Render pod logs.

    :param logs: The logs!
    :param header: Text to associate with the logs.
    """
    console.rule(f"[yellow]{header}[/yellow]", style="yellow")
    console.print(logs, style="grey58")
    console.rule(style="yellow")


def make_progress_bar(
    timeout_seconds: int, polling_freq_seconds: int = DEFAULT_K8S_POLLING_FREQ
) -> Progress:
    """Configure progress bar for monitoring stage execution on CLI.

    :param timeout_seconds: The duration after which all stages in a
        step will be deleted.
    :param polling_freq_seconds: The frequency with which the progress
        bar will receive updates, defaults to DEFAULT_K8S_POLLING_FREQ.
    :return: A configured progress bar.
    """
    progress_bar = Progress(
        TextColumn("{task.description}"),
        TextColumn("[bold bright_red]WAIT    "),
        BarColumn(complete_style="red"),
        TaskProgressColumn(),
        refresh_per_second=2,
        transient=True,
    )
    progress_steps = timeout_seconds / polling_freq_seconds
    progress_bar.add_task(_get_progress_description(), total=progress_steps)
    return progress_bar


def update_progress_bar(progress_bar: Progress) -> None:
    """Update progress bar by advancing all tasks one step.

    :param progress_bar: The progress bar whose tasks need advancing.
    """
    progress_info = _get_progress_description()
    for task_id in progress_bar.task_ids:
        progress_bar.update(task_id, advance=1, description=progress_info)


def _get_progress_description() -> str:
    """Compose progress bar description using default log time format."""
    return f"[dim cyan]{datetime.now().strftime(LOG_TIME_FORMAT)}"
