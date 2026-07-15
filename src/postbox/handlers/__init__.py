from aiogram import Router

from postbox.handlers import menu, start

routers: tuple[Router, ...] = (start.router, menu.router)

__all__ = ["routers"]
