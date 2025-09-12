from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Simple health check endpoint for monitoring"""
    try:
        # You can add more sophisticated health checks here
        # like database connectivity, external services, etc.
        
        return JsonResponse({
            "status": "healthy",
            "service": "django-bot-app",
            "timestamp": request.META.get('HTTP_DATE')
        })
    except Exception as e:
        return JsonResponse({
            "status": "unhealthy",
            "error": str(e)
        }, status=500)


@csrf_exempt 
@require_http_methods(["GET"])
def bot_status(request):
    """Check if bot is running and accessible"""
    try:
        # Import here to avoid circular imports
        from bot.loader import bot
        
        # Basic bot info
        bot_info = {
            "status": "running",
            "bot_id": bot.id if hasattr(bot, 'id') else None,
            "username": getattr(bot, 'username', None)
        }
        
        return JsonResponse(bot_info)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "error": str(e)
        }, status=500)
