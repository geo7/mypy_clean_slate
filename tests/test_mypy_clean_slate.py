from __future__ import annotations

import pathlib
import textwrap

from mypy_clean_slate import __version__, main


def test_version() -> None:
    assert __version__ == "0.1.3"


def test_mypy_clean_slate_usage() -> None:
    # atm this is a pretty broad usage test - just checks that things are, pretty much,
    # working as expected.
    py_file_before_fix = textwrap.dedent(
        """
    from __future__ import annotations


    def add(*, arg_1, arg_2):
        return arg_1 + arg_2


    add(arg_1=1, arg_2="s")


    def useless_sub(*, arg_1: float, arg_2: Sequence):
        return add(arg_1=arg_1, arg_2="what") - arg_2


    useless_sub(arg_1=3, arg_2=4)
    useless_sub(arg_1=3, arg_2="4")
    """
    ).strip()

    py_file_after_fix = textwrap.dedent(
        """
    from __future__ import annotations


    def add(*, arg_1, arg_2): # type: ignore[no-untyped-def]
        return arg_1 + arg_2


    add(arg_1=1, arg_2="s") # type: ignore[no-untyped-call]


    def useless_sub(*, arg_1: float, arg_2: Sequence): # type: ignore[no-untyped-def, name-defined]
        return add(arg_1=arg_1, arg_2="what") - arg_2 # type: ignore[no-untyped-call]


    useless_sub(arg_1=3, arg_2=4)
    useless_sub(arg_1=3, arg_2="4")
    """
    ).strip()

    python_file = pathlib.Path("file_to_test.py")
    python_file.write_text(py_file_before_fix)
    # there's probably a much nicer way to write these tests.
    report_output = pathlib.Path("testing_report_output.txt")
    report_output.write_text(main.generate_mypy_error_report())

    main.add_type_ignores(report_output=report_output)

    assert python_file.read_text().strip() == py_file_after_fix

    # clean up
    report_output.unlink()
    python_file.unlink()
