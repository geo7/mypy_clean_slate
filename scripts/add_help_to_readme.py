"""
Add --help output from cli to README usage section.

Little script to make it easier to keep the README Usage section up to date with
the parsers help output.
"""

from io import StringIO
from pathlib import Path

from mypy_clean_slate.main import create_parser


def cli_help_text() -> str:
    """Get --help from argparse parser."""
    parser = create_parser()
    cli_help = StringIO()
    parser.print_help(file=cli_help)
    return cli_help.getvalue()


def update_readme_cli_help() -> str:
    """Generate README with updated cli --help."""
    result = cli_help_text()
    readme = Path("./README.md").read_text()
    split_string = "[comment]: # (CLI help split)\n"
    splits = readme.split(split_string)
    return splits[0] + split_string + "\n```\n" + result + "\n```\n\n" + split_string + splits[2]


def main() -> int:
    updated_readme = update_readme_cli_help()
    with open("README.md", "w") as f:
        f.write(updated_readme)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
