from aiogram import Router

from postbox.handlers import journal, menu, receive, send, start

routers: tuple[Router, ...] = (start.router, send.router, receive.router, journal.router, menu.router)

__all__ = ["routers"]
