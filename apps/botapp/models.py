from django.db import models


class BotUser(models.Model):
    user_id = models.CharField(max_length=100, unique=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    is_admin = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def __str__(self):
        return self.username or self.full_name or self.user_id

    def make_admin(self):
        self.is_admin = True
        self.save(update_fields=["is_admin"])

    def remove_admin(self):
        self.is_admin = False
        self.save(update_fields=["is_admin"])

    class Meta:
        verbose_name = "Bot User"
        verbose_name_plural = "Bot Users"
        ordering = ["-created_at"]
