from .models import Notification

def theme_mode(request):
    dark_mode = request.session.get('dark_mode', False)
    return {'dark_mode': dark_mode}

def user_notifications(request):
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).order_by('-created_at')[:10]
        return {'notifications': notifications}
    return {'notifications': []}