import logging


def configure_logging(level: str) -> None:
    """Configure concise process logs for local runs and a future VPS."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
