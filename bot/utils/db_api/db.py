from asgiref.sync import sync_to_async
import logging
from apps.botapp.models import BotUser
from bot.data.config import ADMINS


class DB:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_user(self, user_id):
        user = await sync_to_async(BotUser.objects.get)(user_id=user_id)
        return user

    async def create_user(self, user_id, username, first_name, last_name):
        user = await sync_to_async(BotUser.objects.update_or_create)(
            user_id=user_id,
            defaults={
                "username": username,
                "first_name": first_name,
                "last_name": last_name
            }
        )
        return user

    async def update_user(self, user_id, **kwargs):
        user = await self.get_user(user_id)
        for key, value in kwargs.items():
            setattr(user, key, value)
        await sync_to_async(user.save)()
        return user

    async def delete_user(self, user_id):
        user = await self.get_user(user_id)
        await sync_to_async(user.delete)()
        return user
    
    async def user_exists(self, user_id):
        exists = await sync_to_async(BotUser.objects.filter(user_id=user_id).exists)()
        return exists

    async def get_admins_list(self):
        admins = await sync_to_async(BotUser.objects.filter(is_admin=True).values_list('user_id', flat=True))() # type: ignore
        admins_list = list(admins) + ADMINS
        return admins_list
    
    async def is_admin(self, user_id):
        if str(user_id) in ADMINS:
            return True
        is_admin = await sync_to_async(BotUser.objects.filter(user_id=user_id, is_admin=True).exists)() # type: ignore
        return is_admin