#!/bin/bash

echo "Starting ChatX Full-Stack Application..."

# Function to handle cleanup
cleanup() {
    echo "Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start FastAPI backend
echo "Starting FastAPI backend on port 8000..."
cd /app/api
python run.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start Next.js frontend
echo "Starting Next.js frontend on port 3000..."
cd /app/frontend
npm start &
FRONTEND_PID=$!

echo "Both services started successfully!"
echo "Frontend: http://localhost:3000"
echo "Backend: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID