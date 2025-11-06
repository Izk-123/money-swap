from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Agent, AgentWallet

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'agent':
        Agent.objects.create(user=instance)

@receiver(post_save, sender=Agent)
def create_agent_wallets(sender, instance, created, **kwargs):
    if created:
        # Create wallet entries for the agent
        AgentWallet.objects.create(agent=instance.user, service_type='bank')
        AgentWallet.objects.create(agent=instance.user, service_type='mpamba')
        AgentWallet.objects.create(agent=instance.user, service_type='airtel_money')