from __future__ import annotations

import pathlib
import sys

import pytest

from scripts import add_help_to_readme


@pytest.mark.skipif(
    # This test isn't critical to any application logic, and is caught by
    # testing on other versions in CI. Change here is that argparse from >3.9
    # uses 'options' rather than 'optional arguments'. As long as it generates
    # something correctly on _a_ python version I'm fine.
    sys.version_info < (3, 13),
    reason="Changes in argparse output.",
)
def test_readme_cli_help() -> None:
    """Test the README has up to date help output."""

    # For some reason I was getting some whitespace differences when generating
    # in different places, not sure why this was (the content was the same
    # otherwise) so am just comparing without \n or ' '
    def strp(s: str) -> str:
        return s.replace("\n", "").replace(" ", "")

    updated = strp(add_help_to_readme.update_readme_cli_help())
    existing = strp(pathlib.Path("README.md").read_text())
    assert updated == existing
