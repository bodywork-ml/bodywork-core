from typing import Any, Dict, Optional

from rich.console import Console
from rich.table import Table

console = Console(highlight=False, soft_wrap=False)


def print_info(msg: str) -> None:
    """Print an info message."""
    console.print(msg, style="green")


def print_warn(msg: str) -> None:
    """Print a warning message."""
    console.print(msg, style="red")


def print_dict(the_dict: Dict[str, Any], table_name: Optional[str] = None) -> None:
    """Render dict as a table in terminal.

    :the_dict: The dictionary to render.
    :name: Table name, default to None.
    """
    table = Table(title=f"{table_name if table_name else ''}", title_style="bold")
    table.add_column("[yellow]Field[/yellow]", style="bold purple")
    table.add_column("[yellow]Value[/yellow]", style="bold green")
    for field, value in the_dict.items():
        table.add_row(str(field), str(value))
    console.print(table)


def print_pod_logs(logs: str, name: str) -> None:
    """Render pod lods.

    :logs: The logs!
    :name: The name of the pod associated with the logs.
    """
    console.rule(f"[yellow]logs {name} stage[/yellow]", style="yellow")
    console.print(logs, style="grey58")
    console.rule(style="yellow")
