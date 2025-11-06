#!/usr/bin/env python
import os
import sys
import django

def setup_sample_data():
    """Create sample data for testing"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'money_swapv2.settings')
    django.setup()
    
    from django.contrib.auth import get_user_model
    from swap_app.models import User, Agent, Account
    
    User = get_user_model()
    
    # Create sample client
    client, created = User.objects.get_or_create(
        username='client1',
        defaults={
            'email': 'client1@example.com',
            'phone_number': '0881234567',
            'role': 'client',
            'is_verified': True,
            'location_address': 'Blantyre, Malawi'
        }
    )
    if created:
        client.set_password('password123')
        client.save()
        print("Created sample client: client1 / password123")
    
    # Create sample agent
    agent_user, created = User.objects.get_or_create(
        username='agent1',
        defaults={
            'email': 'agent1@example.com',
            'phone_number': '0997654321',
            'role': 'agent',
            'is_verified': True,
            'location_address': 'Lilongwe, Malawi'
        }
    )
    if created:
        agent_user.set_password('password123')
        agent_user.save()
        
        # Create agent profile
        agent, _ = Agent.objects.get_or_create(
            user=agent_user,
            defaults={
                'verified': True,
                'is_online': True,
                'float_mpamba': 50000,
                'float_airtel': 30000,
                'rating': 4.8
            }
        )
        print("Created sample agent: agent1 / password123")
    
    # Create admin user
    admin, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@moneyswap.mw',
            'phone_number': '0880000000',
            'role': 'admin',
            'is_verified': True,
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin.set_password('admin123')
        admin.save()
        print("Created admin user: admin / admin123")
    
    print("\nSample data created successfully!")
    print("\nLogin credentials:")
    print("Client: client1 / password123")
    print("Agent: agent1 / password123") 
    print("Admin: admin / admin123")

if __name__ == '__main__':
    setup_sample_data()