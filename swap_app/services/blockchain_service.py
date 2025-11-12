import hashlib
import json
from datetime import datetime
from django.utils import timezone
from ..models import Block, BlockchainEvent

class BlockchainService:
    """Service for blockchain operations - Enhanced for no-money-holding model"""
    
    def __init__(self):
        self.difficulty = 4
    
    def record_swap_created(self, swap, actor):
        """Record swap creation - no money involved"""
        event_payload = {
            'swap_ref': swap.reference,
            'amount': float(swap.amount),
            'client_id': str(swap.client.id),
            'agent_id': str(swap.agent.id),
            'from_service': swap.from_service,
            'to_service': swap.to_service,
            'calculated_fee': float(swap.platform_fee + swap.agent_fee),
            'timestamp': str(timezone.now()),
            'money_flow': 'direct_client_to_agent',  # Important: no platform holding
            'legal_note': 'platform_does_not_hold_funds'
        }
        return self._submit_event('SWAP_CREATED', swap.reference, event_payload, str(actor.id))
    
    def record_swap_reserved(self, swap, actor):
        """Record swap reservation"""
        event_payload = {
            'swap_ref': swap.reference,
            'agent_response_time': swap.agent_response_at.isoformat(),
            'timestamp': str(timezone.now()),
            'money_flow': 'direct_client_to_agent'
        }
        return self._submit_event('SWAP_RESERVED', swap.reference, event_payload, str(actor.id))
    
    def record_swap_paid_bank(self, swap, actor):
        """Record bank payment - client to agent directly"""
        event_payload = {
            'swap_ref': swap.reference,
            'client_proof_uploaded_at': swap.client_proof_uploaded_at.isoformat(),
            'timestamp': str(timezone.now()),
            'money_flow': 'direct_client_to_agent',
            'transfer_type': 'client_to_agent_direct'
        }
        return self._submit_event('SWAP_PAID_BANK', swap.reference, event_payload, str(actor.id))
    
    def record_swap_sent_wallet(self, swap, actor):
        """Record wallet send - agent to client directly"""
        event_payload = {
            'swap_ref': swap.reference,
            'agent_proof_uploaded_at': swap.agent_proof_uploaded_at.isoformat(),
            'timestamp': str(timezone.now()),
            'money_flow': 'direct_agent_to_client',
            'transfer_type': 'agent_to_client_direct'
        }
        return self._submit_event('SWAP_SENT_WALLET', swap.reference, event_payload, str(actor.id))
    
    def record_swap_completed(self, swap, actor):
        """Record swap completion - fees recorded but not collected"""
        event_payload = {
            'swap_ref': swap.reference,
            'platform_fee_owed': float(swap.platform_fee),
            'agent_fee_earned': float(swap.agent_fee),
            'settlement_status': 'monthly_invoice',  # Fees settled externally
            'timestamp': str(timezone.now()),
            'money_flow': 'complete_direct_transfer',
            'legal_note': 'fees_settled_externally_no_platform_holding'
        }
        return self._submit_event('SWAP_COMPLETED', swap.reference, event_payload, str(actor.id))
    
    def record_dispute_opened(self, dispute, actor):
        """Record dispute opening"""
        event_payload = {
            'swap_ref': dispute.swap_request.reference,
            'reason': dispute.reason,
            'severity': dispute.severity,
            'timestamp': str(timezone.now())
        }
        return self._submit_event('DISPUTE_OPENED', dispute.swap_request.reference, event_payload, str(actor.id))
    
    def _submit_event(self, event_type, entity_ref, payload, actor):
        """Submit event to blockchain"""
        # Hash the payload
        payload_hash = self._calculate_hash(payload)
        
        # Create event
        event_data = {
            'event_type': event_type,
            'timestamp': str(timezone.now()),
            'entity_ref': entity_ref,
            'payload_hash': payload_hash,
            'actor': actor
        }
        
        # For prototype, we'll simply store in database
        # In production, this would involve mining a block
        return self._store_event(event_data)
    
    def _calculate_hash(self, data):
        """Calculate SHA-256 hash of data"""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()
    
    def _store_event(self, event_data):
        """Store event in database (simplified for prototype)"""
        # Get or create latest block
        latest_block = Block.objects.order_by('-index').first()
        if not latest_block:
            # Create genesis block
            latest_block = self._create_genesis_block()
        
        # For prototype, we'll add events to the latest block
        # In production, you would mine a new block
        event = BlockchainEvent.objects.create(
            block=latest_block,
            event_id=f"evt{hashlib.sha256(json.dumps(event_data).encode()).hexdigest()[:16]}",
            event_type=event_data['event_type'],
            timestamp=event_data['timestamp'],
            entity_ref=event_data['entity_ref'],
            payload_hash=event_data['payload_hash'],
            actor=event_data['actor']
        )
        
        return event
    
    def _create_genesis_block(self):
        """Create the first block in the chain"""
        genesis_data = {
            "index": 0,
            "timestamp": str(timezone.now()),
            "previous_hash": "0" * 64,
            "events": [],
            "message": "MoneySwap Genesis Block - No Money Holding Model",
            "legal_note": "Platform acts as matching service only - No funds held"
        }
        
        block_hash = self._calculate_hash(genesis_data)
        
        return Block.objects.create(
            index=0,
            timestamp=timezone.now(),
            previous_hash="0" * 64,
            block_hash=block_hash,
            nonce=0,
            node_signature="genesis",
            validator_signatures=[]
        )
    
    def get_status(self):
        """Get blockchain status"""
        latest_block = Block.objects.order_by('-index').first()
        total_events = BlockchainEvent.objects.count()
        
        return {
            'latest_block_index': latest_block.index if latest_block else 0,
            'total_blocks': Block.objects.count(),
            'total_events': total_events,
            'integrity_check': self._verify_blockchain_integrity()
        }
    
    def _verify_blockchain_integrity(self):
        """Verify blockchain integrity"""
        blocks = Block.objects.order_by('index')
        previous_hash = "0" * 64
        
        for block in blocks:
            if block.previous_hash != previous_hash:
                return False
            # In production, you would verify the block hash here
            previous_hash = block.block_hash
        
        return True