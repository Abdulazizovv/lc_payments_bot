from aiogram import executor
from django.core.management.base import BaseCommand

from bot import filters
from bot import middlewares
from bot import handlers  # Import handlers

from bot.loader import dp
from bot.utils.notify_admins import on_startup_notify
from bot.utils.set_bot_commands import set_default_commands


class Command(BaseCommand):
    help = 'Telegram-bot'

    def handle(self, *args, **options):
        # Set up filters and middlewares
        filters.setup(dp)
        middlewares.setup(dp)
        
        self.stdout.write(self.style.SUCCESS('Starting Telegram bot...'))
        
        # Start the bot with polling
        executor.start_polling(dp, on_startup=on_startup, skip_updates=True, fast=True)


async def on_startup(dispatcher):
    # Set up bot commands
    await set_default_commands(dispatcher)
    
    # Notify admins that bot has started
    await on_startup_notify(dispatcher)
