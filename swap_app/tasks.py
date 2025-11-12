from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import SwapRequest, Notification, Agent

@shared_task
def send_sms_notification(phone_number, message):
    """Send SMS notification (placeholder for SMS integration)"""
    # In production, integrate with SMS gateway like Africa's Talking
    print(f"📱 SMS to {phone_number}: {message}")
    return f"SMS sent to {phone_number}"

@shared_task
def send_email_notification(email, subject, message):
    """Send email notification"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return f"Email sent to {email}"
    except Exception as e:
        print(f"Email sending failed: {e}")
        return f"Email failed for {email}"

@shared_task
def send_whatsapp_notification(phone_number, message):
    """Send WhatsApp notification (placeholder)"""
    print(f"💬 WhatsApp to {phone_number}: {message}")
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
        swap.status = 'EXPIRED'
        swap.save()
        
        # Notify client
        Notification.objects.create(
            user=swap.client,
            swap_request=swap,
            type='system',
            message=f"Swap request expired - agent didn't respond in time"
        )
    
    return f"Auto-expired {expired_swaps.count()} pending requests"

@shared_task
def auto_cancel_accepted_timeout():
    """Automatically cancel swaps where client didn't upload proof"""
    timeout = timezone.now() - timedelta(hours=2)
    timeout_swaps = SwapRequest.objects.filter(
        status='ACCEPTED',
        agent_response_at__lt=timeout
    ).select_related('agent__user', 'client')
    
    for swap in timeout_swaps:
        swap.status = 'CANCELLED'
        swap.save()
        
        # Notify both parties
        Notification.objects.create(
            user=swap.client,
            swap_request=swap,
            type='system',
            message=f"Swap cancelled - payment proof not uploaded in time"
        )
        Notification.objects.create(
            user=swap.agent.user,
            swap_request=swap,
            type='system',
            message=f"Swap cancelled - client didn't upload proof in time"
        )
    
    return f"Auto-cancelled {timeout_swaps.count()} accepted swaps"

@shared_task
def update_agent_trust_scores():
    """Update agent trust scores based on recent performance"""
    agents = Agent.objects.all()
    for agent in agents:
        # Trust score is automatically calculated via model properties
        # This task just ensures the score is up to date
        agent.save()
    
    return "Updated agent trust scores"

@shared_task
def generate_monthly_invoices():
    """Generate monthly invoices for platform fees"""
    from .services.fee_settlement_service import FeeSettlementService
    from datetime import datetime
    
    previous_month = datetime.now().replace(day=1) - timedelta(days=1)
    previous_month = previous_month.replace(day=1)
    
    agents = Agent.objects.filter(verified=True)
    for agent in agents:
        invoice = FeeSettlementService.generate_agent_invoice(agent, previous_month)
        
        if invoice['total_platform_fee'] > 0:
            # Send invoice email
            send_email_notification.delay(
                agent.user.email,
                f"MoneySwap Invoice - {invoice['period']}",
                f"""
                Invoice Number: {invoice['invoice_number']}
                Period: {invoice['period']}
                Total Swaps: {invoice['total_swaps']}
                Total Volume: MWK {invoice['total_volume']:,.2f}
                Platform Fee Due: MWK {invoice['total_platform_fee']:,.2f}
                
                Please settle this invoice within 30 days.
                
                Thank you for using MoneySwap!
                """
            )
    
    return f"Generated invoices for {agents.count()} agents"

@shared_task
def cleanup_old_notifications():
    """Remove notifications older than 30 days"""
    cutoff_date = timezone.now() - timedelta(days=30)
    deleted_count = Notification.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    return f"Cleaned up {deleted_count} old notifications"