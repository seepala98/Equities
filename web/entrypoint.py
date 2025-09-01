#!/usr/bin/env python3
"""
Cross-platform Django application entrypoint script.

This Python script replaces entrypoint.sh for better cross-platform compatibility.
Works on Windows, Linux, macOS, and any system with Python 3.6+.
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

def log(message, level="INFO"):
    """Simple logging function."""
    print(f"[{level}] {message}")

def wait_for_database(host, port, timeout=60):
    """
    Wait for database to be ready using Python sockets.
    Much more reliable than shell scripts and works on all platforms.
    """
    if not host:
        log("No database host specified, skipping database check")
        return True
    
    log(f"Waiting for database at {host}:{port}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)  # 1 second timeout
                result = sock.connect_ex((host, int(port)))
                if result == 0:
                    log(f"✅ Database at {host}:{port} is ready!")
                    return True
        except (socket.error, ValueError) as e:
            log(f"Database connection attempt failed: {e}", "DEBUG")
        
        log("Database is unavailable - sleeping for 1 second")
        time.sleep(1)
    
    log(f"❌ Database at {host}:{port} failed to become ready after {timeout}s", "ERROR")
    return False

def run_command(cmd, description, allow_failure=False):
    """
    Run a shell command with proper error handling.
    Cross-platform compatible.
    """
    log(f"Running: {description}")
    log(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    
    try:
        if isinstance(cmd, str):
            # Handle string commands (like with shell=True)
            result = subprocess.run(cmd, shell=True, check=True, 
                                  capture_output=True, text=True)
        else:
            # Handle list commands (preferred)
            result = subprocess.run(cmd, check=True, 
                                  capture_output=True, text=True)
        
        if result.stdout:
            log(f"Output: {result.stdout.strip()}")
        
        log(f"✅ {description} completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        error_msg = f"❌ {description} failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\nError output: {e.stderr.strip()}"
        if e.stdout:
            error_msg += f"\nStandard output: {e.stdout.strip()}"
        
        log(error_msg, "ERROR" if not allow_failure else "WARNING")
        
        if allow_failure:
            log(f"Continuing despite failure (allow_failure=True)")
            return False
        else:
            sys.exit(1)
    
    except Exception as e:
        log(f"❌ Unexpected error running {description}: {e}", "ERROR")
        if not allow_failure:
            sys.exit(1)
        return False

def main():
    """Main entrypoint logic."""
    log("🚀 Starting Django application entrypoint")
    log(f"Python version: {sys.version}")
    log(f"Platform: {sys.platform}")
    log(f"Working directory: {os.getcwd()}")
    
    # Get environment variables
    postgres_host = os.getenv('POSTGRES_HOST', '')
    postgres_port = os.getenv('POSTGRES_PORT', '5432')
    
    # Log environment info
    log(f"Database host: {postgres_host or 'Not specified'}")
    log(f"Database port: {postgres_port}")
    
    # Step 1: Wait for database if specified
    if postgres_host:
        if not wait_for_database(postgres_host, postgres_port):
            log("Failed to connect to database - exiting", "ERROR")
            sys.exit(1)
    
    # Step 2: Run Django migrations
    migrate_cmd = [sys.executable, 'manage.py', 'migrate', '--noinput']
    run_command(migrate_cmd, "Django database migrations")
    
    # Step 3: Collect static files (allow failure for development)
    static_cmd = [sys.executable, 'manage.py', 'collectstatic', '--noinput']
    run_command(static_cmd, "Django static file collection", allow_failure=True)
    
    # Step 4: Start Django development server
    log("🌟 Starting Django development server...")
    server_cmd = [sys.executable, 'manage.py', 'runserver', '0.0.0.0:8000']
    
    try:
        # Use exec equivalent - replace current process
        log(f"Executing: {' '.join(server_cmd)}")
        os.execvp(sys.executable, server_cmd)
    except Exception as e:
        log(f"❌ Failed to start Django server: {e}", "ERROR")
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("👋 Received interrupt signal - shutting down gracefully")
        sys.exit(0)
    except Exception as e:
        log(f"💥 Unexpected error in entrypoint: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)
