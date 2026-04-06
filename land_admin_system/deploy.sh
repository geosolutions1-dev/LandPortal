#!/bin/bash
# deploy.sh

echo "🚀 Starting deployment process..."

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo "🗄️ Initializing database..."
python -c "from database import init_db; init_db()"

# Start the application
echo "🌐 Starting application..."
gunicorn app:app