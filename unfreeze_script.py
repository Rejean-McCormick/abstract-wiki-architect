import psutil
import platform
import sys
import subprocess
import os
import datetime

# CONFIG: We are looking for python processes to kill
TARGET_PROCESS_NAME = 'python' 

def kill_and_restart():
    print(f"--- ACTION: ATTEMPTING TO UNFREEZE ({TARGET_PROCESS_NAME}) ---")
    killed_count = 0
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if process matches python and is NOT this specific script
            if TARGET_PROCESS_NAME in proc.info['name'] and proc.info['pid'] != current_pid:
                p = psutil.Process(proc.info['pid'])
                p.terminate()
                try:
                    p.wait(timeout=3)
                except psutil.TimeoutExpired:
                    p.kill()
                print(f"Process PID {proc.info['pid']} terminated.")
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if killed_count == 0:
        print(f"No external '{TARGET_PROCESS_NAME}' process found to kill.")
    else:
        print(f"Successfully terminated {killed_count} process(es).")
    print("-" * 30 + "\n")

def get_system_diagnostics():
    print("--- RETRIEVE: SYSTEM DIAGNOSTICS ---")
    print(f"Time: {datetime.datetime.now()}")
    print(f"OS: {platform.system()} {platform.release()}")
    
    print(f"\n[Resources]")
    mem = psutil.virtual_memory()
    print(f"Total RAM: {mem.total / (1024**3):.2f} GB")
    print(f"Memory Usage: {mem.percent}%")
    print(f"CPU Usage: {psutil.cpu_percent(interval=1)}%")
    
    print("-" * 30)
    print("COPY ALL TEXT ABOVE AND PASTE BACK")

if __name__ == "__main__":
    kill_and_restart()
    get_system_diagnostics()
