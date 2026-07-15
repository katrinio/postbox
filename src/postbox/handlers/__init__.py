from aiogram import Router

from postbox.handlers import menu, receive, send, start

routers: tuple[Router, ...] = (start.router, send.router, receive.router, menu.router)

__all__ = ["routers"]
