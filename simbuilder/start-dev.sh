#!/bin/bash
# Bash script to run both Django backend and Vite frontend

set -e

echo "============================================================"
echo "🌟 SAlly Simbuilder Development Server"
echo "============================================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Check if pnpm is installed
if ! command -v pnpm &> /dev/null; then
    echo "❌ Error: pnpm is not installed"
    echo "   Install it with: npm install -g pnpm"
    exit 1
fi

# Install frontend dependencies if needed
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd "$FRONTEND_DIR"
    pnpm install
    cd "$SCRIPT_DIR"
    echo "✅ Frontend dependencies installed"
    echo ""
fi

echo "🚀 Starting servers..."
echo "   Backend:  http://0.0.0.0:8000"
echo "   Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "============================================================"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "👋 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Start Django backend
cd "$SCRIPT_DIR"
python manage.py runserver 0.0.0.0:8000 &
BACKEND_PID=$!

# Start Vite frontend
cd "$FRONTEND_DIR"
pnpm run dev &
FRONTEND_PID=$!

# Wait for both processes
wait

