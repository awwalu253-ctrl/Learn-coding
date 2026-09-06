#!/bin/bash
# build.sh

echo "🔧 Installing system dependencies for PostgreSQL..."

# Install PostgreSQL development headers
apt-get update -y
apt-get install -y gcc postgresql-client libpq-dev

echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build complete!"