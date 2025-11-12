#!/bin/bash
# MoneySwap v2 Setup Script

set -e

echo "🚀 Starting MoneySwap v2 Setup..."

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 8), 'Python 3.8+ required'; print('✓ Python version OK')"

# Create virtual environment
echo "📦 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup environment
echo "🔧 Configuring environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Please edit .env file with your settings!"
    echo "   Then run: python manage.py migrate"
    exit 1
fi

# Load environment
set -a
source .env
set +a

# Database setup
echo "🗄️  Setting up database..."
python manage.py migrate

# Initialize blockchain
echo "⛓️  Initializing blockchain..."
python manage.py init_blockchain

# Seed initial data
echo "🌱 Seeding initial data..."
python manage.py seed_agents

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Setup complete!"
echo ""
echo "🚀 To start the application:"
echo "   source venv/bin/activate"
echo "   ./start_server.sh"
echo ""
echo "🔍 Create admin user:"
echo "   python manage.py createsuperuser"