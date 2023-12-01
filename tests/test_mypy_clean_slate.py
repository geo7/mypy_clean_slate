from __future__ import annotations

import pathlib
import textwrap

from mypy_clean_slate import __version__, main


def test_version() -> None:
    # Ensure toml version is in sync with package version.
    with open("pyproject.toml") as f:
        pyproject_version = [line for line in f.readlines() if line.startswith("version = ")]
    assert len(pyproject_version) == 1
    assert pyproject_version[0].strip().split(" = ")[-1].replace('"', "") == __version__


def test_mypy_clean_slate_usage(tmp_path: pathlib.Path) -> None:
    # atm this is a pretty broad usage test - just checks that things are, pretty much,
    # working as expected.
    py_file_before_fix = textwrap.dedent(
        """
    from __future__ import annotations


    def add(*, arg_1, arg_2):
        return arg_1 + arg_2


    add(arg_1=1, arg_2="s") # inline comment.


    def useless_sub(*, arg_1: float, arg_2: Sequence):
        return add(arg_1=arg_1, arg_2="what") - arg_2


    useless_sub(arg_1=3, arg_2=4)
    useless_sub(arg_1=3, arg_2="4")
    """,
    ).strip()

    py_file_after_fix = textwrap.dedent(
        """
from __future__ import annotations


def add(*, arg_1, arg_2):  # type: ignore[no-untyped-def]
    return arg_1 + arg_2


add(arg_1=1, arg_2="s")   # type: ignore[no-untyped-call] # inline comment.


def useless_sub(*, arg_1: float, arg_2: Sequence):  # type: ignore[no-untyped-def, name-defined]
    return add(arg_1=arg_1, arg_2="what") - arg_2  # type: ignore[no-untyped-call]


useless_sub(arg_1=3, arg_2=4)
useless_sub(arg_1=3, arg_2="4")
    """.strip(),
    )

    python_file = pathlib.Path(tmp_path, "file_to_check.py")
    python_file.write_text(py_file_before_fix, encoding="utf8")

    # there's probably a much nicer way to write these tests.
    report_output = pathlib.Path(tmp_path, "testing_report_output.txt")
    report_output.write_text(
        main.generate_mypy_error_report(path_to_code=python_file),
        encoding="utf8",
    )

    main.add_type_ignores(report_output=report_output)
    assert python_file.read_text(encoding="utf8").strip() == py_file_after_fix
