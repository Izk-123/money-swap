from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import SwapRequest, Notification, Agent, TransactionLog

@shared_task
def send_sms_notification(phone_number, message):
    """Send SMS notification (placeholder for SMS integration)"""
    print(f"SMS to {phone_number}: {message}")
    return f"SMS sent to {phone_number}"

@shared_task
def send_whatsapp_notification(phone_number, message):
    """Send WhatsApp notification (placeholder)"""
    print(f"WhatsApp to {phone_number}: {message}")
    return f"WhatsApp sent to {phone_number}"

@shared_task
def notify_pending_requests():
    """Send reminder notifications for pending swap requests"""
    timeout = timezone.now() - timedelta(minutes=10)
    pending_swaps = SwapRequest.objects.filter(
        status='PENDING',
        created_at__lt=timeout
    ).select_related('agent__user', 'client')
    
    for swap in pending_swaps:
        # Notify agent again
        Notification.objects.create(
            user=swap.agent.user,
            swap_request=swap,
            type='system',
            message=f"Reminder: You have a pending swap request from {swap.client.username}"
        )
        
        # Send SMS reminder
        send_sms_notification.delay(
            swap.agent.user.phone_number,
            f"Reminder: Pending swap request MWK {swap.amount} from {swap.client.username}"
        )
    
    return f"Sent reminders for {pending_swaps.count()} pending requests"

@shared_task
def auto_reject_expired_requests():
    """Automatically reject swap requests that weren't responded to"""
    timeout = timezone.now() - timedelta(minutes=30)
    expired_swaps = SwapRequest.objects.filter(
        status='PENDING',
        created_at__lt=timeout
    ).select_related('agent__user', 'client')
    
    for swap in expired_swaps:
        swap.status = 'REJECTED'
        swap.save()
        
        # Notify client
        Notification.objects.create(
            user=swap.client,
            swap_request=swap,
            type='swap_rejected',
            message=f"Swap request auto-rejected - agent didn't respond in time"
        )
        
        TransactionLog.objects.create(
            swap_request=swap,
            type='AUTO_REJECTED',
            payload={'reason': 'No response from agent within 30 minutes'}
        )
    
    return f"Auto-rejected {expired_swaps.count()} expired requests"

@shared_task
def update_agent_ratings():
    """Update agent ratings based on completed swaps"""
    agents = Agent.objects.all()
    for agent in agents:
        completed_swaps = agent.swap_requests.filter(status='COMPLETE')
        if completed_swaps.count() > 0:
            # Simple rating: start with 5.0 and adjust based on performance
            agent.rating = 5.0
            agent.save()
    
    return "Updated agent ratings"