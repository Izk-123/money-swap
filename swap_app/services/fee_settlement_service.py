from datetime import datetime, timedelta
from django.db.models import Sum, Count
from decimal import Decimal
from ..models import SwapRequest, Agent

class FeeSettlementService:
    """Handle monthly fee settlements outside the platform - NO MONEY HOLDING"""
    
    @staticmethod
    def generate_agent_invoice(agent, month=None):
        """Generate monthly invoice for agent platform fees"""
        if month is None:
            month = datetime.now().replace(day=1)
        
        start_date = month.replace(day=1)
        if month.month == 12:
            end_date = month.replace(year=month.year+1, month=1, day=1)
        else:
            end_date = month.replace(month=month.month+1, day=1)
        
        # Get completed swaps for the month
        completed_swaps = SwapRequest.objects.filter(
            agent=agent,
            status='COMPLETE',
            completed_at__gte=start_date,
            completed_at__lt=end_date
        )
        
        total_platform_fee = completed_swaps.aggregate(
            total=Sum('platform_fee')
        )['total'] or Decimal('0.00')
        
        total_agent_fee = completed_swaps.aggregate(
            total=Sum('agent_fee')
        )['total'] or Decimal('0.00')
        
        invoice_data = {
            'agent': agent,
            'period': start_date.strftime('%B %Y'),
            'total_swaps': completed_swaps.count(),
            'total_volume': completed_swaps.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_platform_fee': total_platform_fee,
            'total_agent_fee': total_agent_fee,
            'swaps': completed_swaps,
            'due_date': start_date + timedelta(days=30),
            'invoice_number': f"INV-{agent.id}-{start_date.strftime('%Y%m')}",
            'legal_note': 'Platform fees for matching and verification services only - No money holding'
        }
        
        return invoice_data
    
    @staticmethod
    def generate_platform_report(month=None):
        """Generate platform-wide settlement report"""
        if month is None:
            month = datetime.now().replace(day=1)
        
        start_date = month.replace(day=1)
        if month.month == 12:
            end_date = month.replace(year=month.year+1, month=1, day=1)
        else:
            end_date = month.replace(month=month.month+1, day=1)
        
        completed_swaps = SwapRequest.objects.filter(
            status='COMPLETE',
            completed_at__gte=start_date,
            completed_at__lt=end_date
        )
        
        report_data = {
            'period': start_date.strftime('%B %Y'),
            'total_swaps': completed_swaps.count(),
            'total_volume': completed_swaps.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            'total_platform_fee': completed_swaps.aggregate(total=Sum('platform_fee'))['total'] or Decimal('0.00'),
            'total_agent_fee': completed_swaps.aggregate(total=Sum('agent_fee'))['total'] or Decimal('0.00'),
            'agent_breakdown': completed_swaps.values('agent__user__username').annotate(
                total_swaps=Count('id'),
                total_fee=Sum('platform_fee')
            ).order_by('-total_fee'),
            'legal_disclaimer': 'MoneySwap acts as matching service only - No funds held or transmitted'
        }
        
        return report_data