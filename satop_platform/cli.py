import re
import sys
from typing import Annotated

import typer

from satop_platform.core.satop_application import SatOPApplication

# Manually get verbosity level before Typer is loaded
manual_verbosity = 0
for arg in sys.argv:
    if arg == "--verbose":
        manual_verbosity += 1
    if re.match(r"-[a-zA-Z]+", arg):
        for c in arg:
            if c == "v":
                manual_verbosity += 1


cli_app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
app = SatOPApplication(cli=cli_app, log_level=manual_verbosity)
app.plugin_engine.load_plugins()
app.load_cli()


@cli_app.callback()
def main(
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True)] = 0,
):
    app.set_log_level(verbose)


if __name__ == "__main__":
    cli_app()
