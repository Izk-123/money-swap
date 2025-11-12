from django.core.management.base import BaseCommand
from swap_app.services.blockchain_service import BlockchainService
from swap_app.models import Block

class Command(BaseCommand):
    help = 'Initialize blockchain with genesis block'
    
    def handle(self, *args, **options):
        self.stdout.write("⛓️  Initializing MoneySwap Blockchain...")
        
        # Check if blockchain already exists
        existing_blocks = Block.objects.count()
        
        if existing_blocks > 0:
            self.stdout.write(self.style.WARNING(
                f'Blockchain already exists with {existing_blocks} blocks'
            ))
            if input('Reinitialize? (y/N): ').lower() != 'y':
                self.stdout.write('Aborted.')
                return
        
        # Clear existing blocks
        Block.objects.all().delete()
        self.stdout.write('🗑️  Cleared existing blockchain data')
        
        # Initialize blockchain service
        blockchain_service = BlockchainService()
        
        # Create genesis block
        genesis_block = blockchain_service._create_genesis_block()
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Created genesis block: {genesis_block.block_hash}'
        ))
        
        # Add some sample events to demonstrate the system
        from swap_app.models import User, Agent
        from django.utils import timezone
        
        try:
            # Get admin user for sample events
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                # Record system initialization event
                blockchain_service._submit_event({
                    'event_type': 'SYSTEM_INITIALIZED',
                    'timestamp': str(timezone.now()),
                    'entity_ref': 'system',
                    'payload_hash': blockchain_service._calculate_hash({'action': 'blockchain_init'}),
                    'actor': str(admin_user.id)
                })
                
                self.stdout.write('✅ Recorded system initialization event')
            
            # Display blockchain status
            status = blockchain_service.get_status()
            self.stdout.write("\n" + "📊 Blockchain Status".center(40, '='))
            self.stdout.write(f"Latest Block: #{status['latest_block_index']}")
            self.stdout.write(f"Total Blocks: {status['total_blocks']}")
            self.stdout.write(f"Total Events: {status['total_events']}")
            self.stdout.write(f"Integrity: {'✅ Verified' if status['integrity_check'] else '❌ Compromised'}")
            
            self.stdout.write(self.style.SUCCESS(
                '\n🎉 Blockchain initialization complete!'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during initialization: {e}'))