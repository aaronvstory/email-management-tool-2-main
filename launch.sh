#!/bin/bash
# ============================================================
#    EMAIL MANAGEMENT TOOL - QUICK LAUNCHER (macOS)
# ============================================================
#    One-click launcher that starts the app and opens browser
# ============================================================

clear

echo ""
echo "============================================================"
echo "   EMAIL MANAGEMENT TOOL - PROFESSIONAL LAUNCHER (macOS)"
echo "============================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH!"
    echo "Please install Python 3.8 or higher."
    read -p "Press Enter to exit..."
    exit 1
fi

# Check for port conflicts and clean up if needed
echo "[PREFLIGHT] Checking for port conflicts..."

# Check port 5001 (Flask)
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "[WARNING] Port 5001 is in use. Checking if it's our application..."

    # Try to access health endpoint
    if curl -s http://localhost:5001/healthz >/dev/null 2>&1; then
        echo "[INFO] Application is already running and healthy!"
        echo ""
        echo "Opening dashboard in browser..."
        sleep 2
        open http://localhost:5001
        echo ""
        echo "[OK] Browser launched!"
        sleep 3
        exit 0
    else
        echo "[WARNING] Port 5001 occupied by unresponsive process."
        echo "[ACTION] Attempting safe cleanup..."

        # Kill only our Python processes running simple_app.py
        for pid in $(lsof -ti :5001); do
            if ps -p $pid -o command= | grep -q "simple_app.py"; then
                kill -9 $pid 2>/dev/null
            fi
        done
        sleep 2
    fi
fi

# Check port 8587 (SMTP Proxy)
if lsof -Pi :8587 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "[WARNING] Port 8587 is in use. Attempting safe cleanup..."

    for pid in $(lsof -ti :8587); do
        if ps -p $pid -o command= | grep -q "simple_app.py"; then
            kill -9 $pid 2>/dev/null
        fi
    done
    sleep 2
fi

echo "[OK] Ports are clear!"

echo "[STARTING] Email Management Tool..."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the Flask application in background
echo "[1/3] Starting Flask application..."
nohup python3 simple_app.py > /dev/null 2>&1 &

# Wait for application to initialize
echo "[2/3] Waiting for services to initialize..."
sleep 5

# Check if app started successfully
if ! lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo ""
    echo "[ERROR] Failed to start application!"
    echo "Please check if port 5001 is available."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[3/3] Opening dashboard in browser..."
echo ""

# Open the dashboard in default browser
open http://localhost:5001

echo "============================================================"
echo "   APPLICATION STARTED SUCCESSFULLY!"
echo "============================================================"
echo ""
echo "   Web Dashboard:  http://localhost:5001"
echo "   SMTP Proxy:     localhost:8587"
echo "   Login:          admin / admin123"
echo ""
echo "   The dashboard has been opened in your browser."
echo "   This script will exit, but the app continues running."
echo ""
echo "   To stop: Run ./email_manager.sh and select 'Stop Application'"
echo "============================================================"
echo ""

read -p "Press Enter to exit..."
