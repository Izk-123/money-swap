from datetime import timezone
from django.db import transaction
from django.utils.crypto import get_random_string
from decimal import Decimal
from typing import Optional

from ..models import SwapRequest, Notification, TransactionLog
from .notification_service import NotificationService
from .blockchain_service import BlockchainService

class SwapService:
    """Service layer for swap business logic - NO MONEY HOLDING"""
    
    @staticmethod
    @transaction.atomic
    def create_swap(client, agent, amount: Decimal, from_service: str, to_service: str, dest_number: str) -> SwapRequest:
        """Create a new swap request - platform NEVER touches money"""
        
        # Validate agent capacity
        if not agent.is_online:
            raise ValueError('Agent is not available')
        
        if not agent.can_accept_swap:
            raise ValueError('Agent has reached daily swap limit')
        
        # Calculate fees for reporting only (no real collection)
        total_fee = max(amount * Decimal('0.006'), Decimal('50'))
        platform_fee = (total_fee * Decimal('0.25')).quantize(Decimal('0.01'))
        agent_fee = (total_fee * Decimal('0.75')).quantize(Decimal('0.01'))
        
        # Generate unique reference
        reference = f"SWAP{get_random_string(8).upper()}"
        
        # Create swap record only
        swap = SwapRequest.objects.create(
            client=client,
            agent=agent,
            amount=amount,
            from_service=from_service,
            to_service=to_service,
            dest_number=dest_number,
            reference=reference,
            platform_fee=platform_fee,  # For reporting only
            agent_fee=agent_fee,        # For reporting only
            status='PENDING'
        )
        
        # Create notification
        NotificationService.notify_agent_new_swap(swap)
        
        # Record on blockchain
        blockchain_service = BlockchainService()
        blockchain_service.record_swap_created(swap, client)
        
        return swap
    
    @staticmethod
    @transaction.atomic
    def accept_swap(swap: SwapRequest, agent) -> None:
        """Agent accepts a swap request"""
        if swap.agent != agent:
            raise ValueError("Agent can only accept their own swap requests")
        
        if not agent.can_accept_swap:
            raise ValueError("Agent has reached daily swap limit")
        
        swap.status = 'ACCEPTED'
        swap.agent_response_at = timezone.now()
        swap.save()
        
        # Update agent response metrics
        response_time = (swap.agent_response_at - swap.created_at).total_seconds()
        swap.agent.update_response_time(response_time)
        
        NotificationService.notify_client_swap_accepted(swap)
        
        # Record on blockchain
        blockchain_service = BlockchainService()
        blockchain_service.record_swap_reserved(swap, agent.user)
    
    @staticmethod
    @transaction.atomic
    def complete_swap(swap: SwapRequest) -> None:
        """Mark swap as complete - fees are settled externally via monthly invoices"""
        swap.status = 'COMPLETE'
        swap.completed_at = timezone.now()
        swap.save()
        
        # Update agent completed swaps count
        swap.agent.completed_swaps += 1
        swap.agent.save()
        
        NotificationService.notify_swap_completed(swap)
        
        # Record on blockchain
        blockchain_service = BlockchainService()
        blockchain_service.record_swap_completed(swap, swap.agent.user)