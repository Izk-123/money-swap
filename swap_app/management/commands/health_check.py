from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from celery import current_app
import redis
import requests
from swap_app.models import Block, SwapRequest, Agent

class Command(BaseCommand):
    help = 'Check system health and dependencies'
    
    def handle(self, *args, **options):
        checks = []
        
        self.stdout.write("🔍 Running MoneySwap Health Check...")
        self.stdout.write("=" * 50)
        
        # Database check
        try:
            connection.ensure_connection()
            checks.append(('✅', 'Database Connection', 'Connected successfully'))
        except Exception as e:
            checks.append(('❌', 'Database Connection', f'Failed: {e}'))
        
        # Cache check
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                checks.append(('✅', 'Cache System', 'Working correctly'))
            else:
                checks.append(('❌', 'Cache System', 'Not responding properly'))
        except Exception as e:
            checks.append(('❌', 'Cache System', f'Failed: {e}'))
        
        # Celery check
        try:
            insp = current_app.control.inspect()
            stats = insp.stats()
            if stats:
                active_workers = len(stats)
                checks.append(('✅', 'Celery Workers', f'{active_workers} workers active'))
            else:
                checks.append(('❌', 'Celery Workers', 'No workers available'))
        except Exception as e:
            checks.append(('❌', 'Celery Workers', f'Failed: {e}'))
        
        # Redis check
        try:
            r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            r.ping()
            checks.append(('✅', 'Redis Server', 'Connected successfully'))
        except Exception as e:
            checks.append(('❌', 'Redis Server', f'Failed: {e}'))
        
        # Blockchain check
        try:
            latest_block = Block.objects.order_by('-index').first()
            if latest_block:
                checks.append(('✅', 'Blockchain', f'Block #{latest_block.index} verified'))
            else:
                checks.append(('⚠️', 'Blockchain', 'No blocks found (run init_blockchain)'))
        except Exception as e:
            checks.append(('❌', 'Blockchain', f'Failed: {e}'))
        
        # Business metrics
        try:
            total_swaps = SwapRequest.objects.count()
            active_agents = Agent.objects.filter(is_online=True, verified=True).count()
            checks.append(('📊', 'Business Metrics', f'{total_swaps} swaps, {active_agents} online agents'))
        except Exception as e:
            checks.append(('❌', 'Business Metrics', f'Failed: {e}'))
        
        # Print results
        self.stdout.write("\n" + "📋 Health Check Results".center(50, '='))
        for status, service, message in checks:
            self.stdout.write(f"{status} {service:<20} {message}")
        
        # Summary
        successful_checks = sum(1 for status, _, _ in checks if status in ['✅', '📊'])
        total_checks = len(checks)
        
        self.stdout.write("\n" + "📈 Summary".center(50, '='))
        self.stdout.write(f"Checks passed: {successful_checks}/{total_checks}")
        
        if all(status in ['✅', '📊'] for status, _, _ in checks):
            self.stdout.write(self.style.SUCCESS('🎉 All systems operational!'))
        elif any(status == '❌' for status, _, _ in checks):
            self.stdout.write(self.style.ERROR('⚠️  Some systems are having issues'))
        else:
            self.stdout.write(self.style.WARNING('ℹ️  Systems mostly operational with warnings'))
        
        # Recommendations
        self.stdout.write("\n" + "💡 Recommendations".center(50, '='))
        if any('Blockchain' in service for _, service, _ in checks if 'No blocks' in _):
            self.stdout.write("• Run: python manage.py init_blockchain")
        
        if any('Celery' in service for _, service, _ in checks if 'No workers' in _):
            self.stdout.write("• Start Celery: celery -A money_swapv2 worker --loglevel=info")
        
        if any('Redis' in service for _, service, _ in checks if 'Failed' in _):
            self.stdout.write("• Start Redis: redis-server")
        
        return 0 if successful_checks == total_checks else 1