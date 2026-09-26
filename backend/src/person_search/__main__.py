"""Development-only API entrypoint."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from person_search import create_app
from person_search.config import parse_boolean_environment
from person_search.observability import configure_logging


def main() -> None:
    """Run Flask's development server with explicit local defaults."""

    load_dotenv()
    configure_logging()
    app = create_app()
    host = os.getenv("PERSON_SEARCH_HOST", "127.0.0.1")
    port = int(os.getenv("PERSON_SEARCH_PORT", "5000"))
    debug = parse_boolean_environment("PERSON_SEARCH_DEBUG", default=False)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
