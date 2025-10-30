import subprocess
import time
import webbrowser
import sys
import os

def kill_simple_app_processes():
    """Kill any running simple_app.py processes"""
    print("Stopping old instances...")
    try:
        # Get all Python processes
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
                              capture_output=True, text=True)

        pids_to_kill = []
        for line in result.stdout.split('\n')[1:]:  # Skip header
            if line.strip():
                parts = line.split(',')
                if len(parts) >= 2:
                    pid = parts[1].strip('"')
                    # Check if this process is running simple_app.py
                    try:
                        cmd_check = subprocess.run(['wmic', 'process', 'where', f'ProcessId={pid}',
                                                  'get', 'CommandLine'],
                                                 capture_output=True, text=True, timeout=2)
                        if 'simple_app.py' in cmd_check.stdout:
                            pids_to_kill.append(pid)
                    except:
                        pass

        # Kill identified processes
        for pid in pids_to_kill:
            try:
                subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                print(f"  Killed PID {pid}")
            except:
                pass

        if pids_to_kill:
            print(f"  Stopped {len(pids_to_kill)} process(es)")
        else:
            print("  No running instances found")

    except Exception as e:
        print(f"  Error during cleanup: {e}")

def start_app():
    """Start the Flask application"""
    print("\nStarting application...")

    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Start in new minimized window
    subprocess.Popen(['python', 'simple_app.py'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NO_WINDOW)

    print("  Application started in background")

def wait_for_app(max_wait=15):
    """Wait for app to be ready"""
    print("\nWaiting for services to initialize...")
    import socket

    for i in range(max_wait):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 5001))
            sock.close()
            if result == 0:
                print(f"  Ready after {i+1} seconds")
                return True
        except:
            pass
        time.sleep(1)
        sys.stdout.write('.')
        sys.stdout.flush()

    print("\n  Warning: App may not be ready yet")
    return False

if __name__ == '__main__':
    print("=" * 60)
    print("  EMAIL MANAGEMENT TOOL - RESTART SCRIPT")
    print("=" * 60)
    print()

    kill_simple_app_processes()
    time.sleep(2)  # Wait for ports to be released
    start_app()

    if wait_for_app():
        print("\nOpening browser...")
        webbrowser.open('http://localhost:5001')
        print("\n" + "=" * 60)
        print("  APPLICATION READY!")
        print("=" * 60)
        print("  Web Dashboard: http://localhost:5001")
        print("  Login: admin / admin123")
        print("=" * 60)
    else:
        print("\nApplication may still be starting...")
        print("Try accessing http://localhost:5001 in a moment")

    print("\nPress Enter to exit...")
    input()
