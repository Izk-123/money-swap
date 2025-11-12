#!/bin/bash
set -e

echo "🚀 Deploying MoneySwap to Production..."

# Pull latest code
git pull origin main

# Install dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart gunicorn
sudo systemctl restart celery
sudo systemctl restart celerybeat

# Clear cache
python manage.py clear_cache

echo "✅ Deployment complete!"