import asyncio

from postbox.app import start_bot


def run() -> None:
    """Run Postbox using long polling."""
    asyncio.run(start_bot())


if __name__ == "__main__":
    run()
