from .models import Notification

def theme_mode(request):
    """Provide dark/light theme mode to templates"""
    dark_mode = request.session.get('dark_mode', False)
    return {'dark_mode': dark_mode}

def user_notifications(request):
    """Provide unread notifications to templates"""
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).order_by('-created_at')[:10]
        return {'notifications': notifications}
    return {'notifications': []}

def platform_info(request):
    """Provide platform information to templates"""
    from django.conf import settings
    return {
        'min_swap_amount': getattr(settings, 'MIN_SWAP_AMOUNT', 50),
        'max_swap_amount': getattr(settings, 'MAX_SWAP_AMOUNT', 50000),
        'enable_kyc': getattr(settings, 'ENABLE_KYC', True),
        'platform_fee_rate': '0.15%',
        'agent_fee_rate': '0.45%',
        'total_fee_rate': '0.6%',
    }