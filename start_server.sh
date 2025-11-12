#!/bin/bash
# Start MoneySwap Development Servers

source venv/bin/activate

echo "Starting Redis Server..."
redis-server --daemonize yes

echo "Starting Celery Worker..."
celery -A money_swapv2 worker --loglevel=info --detach

echo "Starting Celery Beat..."
celery -A money_swapv2 beat --loglevel=info --detach --scheduler django_celery_beat.schedulers:DatabaseScheduler

echo "Starting Django Development Server..."
python manage.py runserver 0.0.0.0:8000