from django.contrib import admin
from apps.botapp.models import BotUser


class BotUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'username', 'full_name', 'is_admin', 'created_at')
    search_fields = ('user_id', 'username', 'first_name', 'last_name')
    list_filter = ('is_admin', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'
    
admin.site.register(BotUser, BotUserAdmin)