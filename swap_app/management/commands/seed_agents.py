from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from swap_app.models import Agent

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed initial agent data for development'
    
    def handle(self, *args, **options):
        agents_data = [
            {
                'username': 'agent_chileka',
                'email': 'agent.chileka@moneyswap.mw',
                'phone_number': '0881000001',
                'location_address': 'Chileka, Blantyre',
                'location_lat': -15.6794,
                'location_lng': 34.9739,
                'bank_name': 'National Bank',
                'bank_account': '1000000001',
                'mpamba_number': '0881000001',
                'airtel_number': '0991000001',
            },
            {
                'username': 'agent_limbe', 
                'email': 'agent.limbe@moneyswap.mw',
                'phone_number': '0881000002',
                'location_address': 'Limbe, Blantyre',
                'location_lat': -15.8000,
                'location_lng': 35.0500,
                'bank_name': 'Standard Bank',
                'bank_account': '2000000001',
                'mpamba_number': '0881000002',
                'airtel_number': '0991000002',
            },
            {
                'username': 'agent_zomba',
                'email': 'agent.zomba@moneyswap.mw',
                'phone_number': '0881000003',
                'location_address': 'Zomba City',
                'location_lat': -15.3761,
                'location_lng': 35.3356,
                'bank_name': 'FDH Bank',
                'bank_account': '3000000001',
                'mpamba_number': '0881000003',
                'airtel_number': '0991000003',
            },
        ]
        
        for agent_data in agents_data:
            user, created = User.objects.get_or_create(
                username=agent_data['username'],
                defaults={
                    'email': agent_data['email'],
                    'phone_number': agent_data['phone_number'],
                    'location_address': agent_data['location_address'],
                    'location_lat': agent_data['location_lat'],
                    'location_lng': agent_data['location_lng'],
                    'role': 'agent',
                    'is_verified': True,
                }
            )
            
            if created:
                user.set_password('agent123')
                user.save()
                
                agent = Agent.objects.get(user=user)
                agent.bank_name = agent_data['bank_name']
                agent.bank_account = agent_data['bank_account']
                agent.mpamba_number = agent_data['mpamba_number']
                agent.airtel_number = agent_data['airtel_number']
                agent.verified = True
                agent.is_online = True
                agent.trust_level = 'trusted'
                agent.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'Created agent: {agent_data["username"]}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Agent already exists: {agent_data["username"]}')
                )