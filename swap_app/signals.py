from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import User, Agent, SwapRequest, Dispute, Notification

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create agent profile when user with agent role is created"""
    if created and instance.role == 'agent':
        Agent.objects.create(user=instance)

@receiver(post_save, sender=SwapRequest)
def update_agent_metrics(sender, instance, **kwargs):
    """Update agent metrics when swap status changes"""
    if instance.status == 'ACCEPTED' and instance.agent_response_at:
        # Calculate response time
        response_time = (instance.agent_response_at - instance.created_at).total_seconds()
        instance.agent.update_response_time(response_time)
    
    elif instance.status == 'COMPLETE':
        # Update completed swaps count
        instance.agent.completed_swaps += 1
        instance.agent.save()

@receiver(post_save, sender=Dispute)
def update_agent_dispute_count(sender, instance, created, **kwargs):
    """Update agent dispute count when dispute is created"""
    if created and instance.swap_request.agent:
        instance.swap_request.agent.add_dispute()

@receiver(pre_save, sender=SwapRequest)
def handle_swap_status_change(sender, instance, **kwargs):
    """Handle notifications for swap status changes"""
    if instance.pk:
        try:
            old_instance = SwapRequest.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Status changed - create notification
                if instance.status == 'ACCEPTED':
                    Notification.objects.create(
                        user=instance.client,
                        swap_request=instance,
                        type='swap_accepted',
                        message=f"Agent {instance.agent.user.username} accepted your swap request"
                    )
                elif instance.status == 'COMPLETE':
                    Notification.objects.create(
                        user=instance.client,
                        swap_request=instance,
                        type='payment_sent',
                        message=f"Swap {instance.reference} completed! You received MWK {instance.net_amount}"
                    )
                    Notification.objects.create(
                        user=instance.agent.user,
                        swap_request=instance,
                        type='payment_sent',
                        message=f"Swap {instance.reference} completed! You earned MWK {instance.agent_fee}"
                    )
        except SwapRequest.DoesNotExist:
            pass

@receiver(post_save, sender=Notification)
def send_real_time_notification(sender, instance, created, **kwargs):
    """Send real-time notifications via email/SMS"""
    if created:
        from .tasks import send_sms_notification, send_email_notification
        # Send SMS for critical notifications
        if instance.type in ['swap_request', 'swap_accepted', 'payment_received']:
            send_sms_notification.delay(
                instance.user.phone_number,
                instance.message
            )
        # Send email for all notifications
        if instance.user.email:
            send_email_notification.delay(
                instance.user.email,
                f"MoneySwap Notification: {instance.get_type_display()}",
                instance.message
            )