#!/usr/bin/env python3
"""
macOS-compatible cleanup and start script for Email Management Tool.
This does NOT replace cleanup_and_start.py (Windows version remains untouched).
"""
import subprocess
import time
import webbrowser
import sys
import os
import signal

def kill_simple_app_processes():
    """Kill any running simple_app.py processes (macOS version)"""
    print("Stopping old instances...")
    try:
        # Find processes using port 5000 and 8587
        ports = [5000, 8587]
        pids_killed = []

        for port in ports:
            try:
                # Use lsof to find processes on port
                result = subprocess.run(
                    ['lsof', '-ti', f':{port}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        pid = pid.strip()
                        if pid:
                            # Check if this is our simple_app.py
                            try:
                                cmd_check = subprocess.run(
                                    ['ps', '-p', pid, '-o', 'command='],
                                    capture_output=True,
                                    text=True,
                                    timeout=2
                                )
                                if 'simple_app.py' in cmd_check.stdout:
                                    os.kill(int(pid), signal.SIGTERM)
                                    time.sleep(0.5)
                                    # Force kill if still running
                                    try:
                                        os.kill(int(pid), signal.SIGKILL)
                                    except ProcessLookupError:
                                        pass  # Already dead
                                    pids_killed.append(pid)
                                    print(f"  Killed PID {pid}")
                            except (subprocess.TimeoutExpired, ValueError, ProcessLookupError):
                                pass
            except subprocess.TimeoutExpired:
                print(f"  Warning: Timeout checking port {port}")
            except Exception as e:
                print(f"  Warning: Error checking port {port}: {e}")

        if pids_killed:
            print(f"  Stopped {len(pids_killed)} process(es)")
        else:
            print("  No running instances found")

    except Exception as e:
        print(f"  Error during cleanup: {e}")

def start_app():
    """Start the Flask application"""
    print("\nStarting application...")

    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Activate virtual environment if it exists
    venv_python = os.path.join(script_dir, 'venv', 'bin', 'python3')
    python_cmd = venv_python if os.path.exists(venv_python) else 'python3'

    # Start in background (detached process)
    subprocess.Popen(
        [python_cmd, 'simple_app.py'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    print("  Application started in background")

def wait_for_app(max_wait=15):
    """Wait for app to be ready"""
    print("\nWaiting for services to initialize...")
    import socket

    for i in range(max_wait):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 5000))
            sock.close()
            if result == 0:
                print(f"  Ready after {i+1} seconds")
                return True
        except Exception:
            pass
        time.sleep(1)
        sys.stdout.write('.')
        sys.stdout.flush()

    print("\n  Warning: App may not be ready yet")
    return False

if __name__ == '__main__':
    print("=" * 60)
    print("  EMAIL MANAGEMENT TOOL - RESTART SCRIPT (macOS)")
    print("=" * 60)
    print()

    kill_simple_app_processes()
    time.sleep(2)  # Wait for ports to be released
    start_app()

    if wait_for_app():
        print("\nOpening browser...")
        webbrowser.open('http://localhost:5000')
        print("\n" + "=" * 60)
        print("  APPLICATION READY!")
        print("=" * 60)
        print("  Web Dashboard: http://localhost:5000")
        print("  Login: admin / admin123")
        print("=" * 60)
    else:
        print("\nApplication may still be starting...")
        print("Try accessing http://localhost:5000 in a moment")

    print("\nPress Enter to exit...")
    input()
