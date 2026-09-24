"""Background worker command placeholder for BE-10."""


def main() -> int:
    """Confirm that the worker entrypoint is installed without starting fake work."""

    print("Person Search worker entrypoint is ready; job processing starts in BE-10.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
