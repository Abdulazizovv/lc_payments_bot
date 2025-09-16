from asgiref.sync import sync_to_async
import logging
from apps.botapp.models import BotUser
from bot.data.config import ADMINS
from typing import List, Tuple, Optional
from django.db.models import Q
from main.models import Student, Enrollment
import math


class DB:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_user(self, user_id):
        user = await sync_to_async(BotUser.objects.get)(user_id=str(user_id))
        return user

    async def create_user(self, user_id, username, first_name, last_name):
        user = await sync_to_async(BotUser.objects.update_or_create)(
            user_id=str(user_id),
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
        exists = await sync_to_async(BotUser.objects.filter(user_id=str(user_id)).exists)()
        return exists

    async def get_admins_list(self):
        admins = await sync_to_async(BotUser.objects.filter(is_admin=True).values_list('user_id', flat=True))() # type: ignore
        admins_list = list(admins) + ADMINS
        return admins_list
    
    async def is_admin(self, user_id):
        if str(user_id) in ADMINS:
            return True
        is_admin = await sync_to_async(BotUser.objects.filter(user_id=str(user_id), is_admin=True).exists)() # type: ignore
        return is_admin

    # -----------------------------
    # Students helpers
    # -----------------------------

    async def get_students(self, page: int = 1, page_size: int = 10, q: Optional[str] = None) -> Tuple[List[Student], int, int, int]:
        """Return (items, total_pages, page, total). Optional q searches by name, phone or id."""
        def _inner():
            qs = Student.objects.all().order_by('full_name', 'id')
            if q:
                text = str(q).strip()
                if text.isdigit():
                    qs = qs.filter(Q(id=int(text)) | Q(full_name__icontains=text) | Q(phone_number__icontains=text))
                else:
                    qs = qs.filter(Q(full_name__icontains=text) | Q(phone_number__icontains=text))
            total = qs.count()
            if page_size <= 0:
                page_size_local = 10
            else:
                page_size_local = page_size
            total_pages = max(1, math.ceil(total / page_size_local))
            page_local = min(max(1, page), total_pages)
            start = (page_local - 1) * page_size_local
            items = list(qs[start:start + page_size_local])
            return items, total_pages, page_local, total
        return await sync_to_async(_inner)()

    async def search_students(self, query: str = "", limit: int = 25) -> List[Student]:
        def _inner():
            qs = Student.objects.all().order_by('full_name', 'id')
            text = (query or '').strip()
            if text:
                if text.isdigit():
                    qs = qs.filter(Q(id=int(text)) | Q(full_name__icontains=text) | Q(phone_number__icontains=text))
                else:
                    qs = qs.filter(Q(full_name__icontains=text) | Q(phone_number__icontains=text))
            return list(qs[:max(1, min(limit, 50))])
        return await sync_to_async(_inner)()

    async def search_enrollments(self, query: str = "", limit: int = 25) -> List[Enrollment]:
        def _inner():
            qs = Enrollment.objects.select_related('student', 'group').filter(is_active=True)
            text = (query or '').strip()
            if text:
                if text.isdigit():
                    qs = qs.filter(
                        Q(student__id=int(text)) |
                        Q(student__full_name__icontains=text) |
                        Q(student__phone_number__icontains=text) |
                        Q(group__title__icontains=text)
                    )
                else:
                    qs = qs.filter(
                        Q(student__full_name__icontains=text) |
                        Q(student__phone_number__icontains=text) |
                        Q(group__title__icontains=text)
                    )
            qs = qs.order_by('student__full_name', 'group__title', 'id')
            return list(qs[:max(1, min(limit, 50))])
        return await sync_to_async(_inner)()