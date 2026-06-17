#!/bin/bash
echo "🚀 Starting NEXA AI Trader..."

# Start backend
echo "📡 Starting Backend API on port 8000..."
cd /home/claude/repo/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# Start frontend
echo "🎨 Starting Frontend on port 3000..."
cd /home/claude/repo/frontend
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "✅ NEXA AI Trader is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Default Admin: admin@nexa.ai / Admin@12345"
echo ""
echo "Press Ctrl+C to stop..."

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
