from aiogram import Router

from postbox.handlers import menu, send, start

routers: tuple[Router, ...] = (start.router, send.router, menu.router)

__all__ = ["routers"]
