# Cross-Platform Django Entrypoint

## Overview

This project uses a **Python-based entrypoint** (`entrypoint.py`) instead of shell scripts for **100% cross-platform compatibility**.

## Why Python Instead of Shell?

### ❌ **Problems with `entrypoint.sh`:**
- **Windows incompatibility**: `#!/bin/sh` doesn't exist on Windows
- **Missing dependencies**: `nc` (netcat) not available on all systems  
- **Path issues**: Different path separators (`/` vs `\`)
- **Error handling**: Shell error handling is inconsistent
- **Debugging**: Hard to debug shell scripts across platforms

### ✅ **Benefits of `entrypoint.py`:**
- **100% cross-platform**: Works on Windows, Linux, macOS, Docker
- **No external dependencies**: Uses only Python standard library
- **Better error handling**: Proper exceptions and logging
- **Easy to debug**: Standard Python debugging tools
- **Type safety**: Python's type system helps catch errors
- **Maintainable**: More readable and easier to extend

## Features

### 🔌 **Smart Database Connectivity**
- Uses Python `socket` module instead of `nc` command
- Configurable timeout (default: 60 seconds)
- Graceful handling when no database specified
- Cross-platform socket connectivity

### 📝 **Comprehensive Logging**
- Structured log messages with levels (INFO, WARNING, ERROR)
- Platform and environment information logging
- Command output capture and display
- Error details with traceback

### 🛡️ **Robust Error Handling**
- Subprocess management with proper error capture
- Optional failure tolerance for non-critical commands
- Graceful shutdown on interrupts
- Detailed error reporting

### ⚡ **Django Integration**
- Database migrations with `--noinput`
- Static file collection with failure tolerance
- Development server startup with proper process replacement

## Usage

### In Docker (Recommended)
```dockerfile
# Dockerfile automatically uses the Python entrypoint
ENTRYPOINT ["python", "/app/entrypoint.py"]
```

### Manual Execution
```bash
# From the web directory
python entrypoint.py
```

### Environment Variables
```bash
# Database configuration (optional)
export POSTGRES_HOST=localhost    # Database host
export POSTGRES_PORT=5432        # Database port (default: 5432)

# Django settings
export DJANGO_SETTINGS_MODULE=project.settings
```

## Architecture

### 🔄 **Execution Flow**
1. **Environment Detection**: Log system info and environment
2. **Database Wait**: Check database connectivity (if specified)
3. **Migrations**: Run Django database migrations
4. **Static Files**: Collect static files (non-critical)
5. **Server Start**: Launch Django development server

### 🏗️ **Code Structure**
```python
entrypoint.py
├── log()                    # Structured logging
├── wait_for_database()      # Cross-platform DB connectivity
├── run_command()            # Subprocess management
└── main()                   # Main execution flow
```

## Development

### Testing Locally
```bash
# Syntax check
python -m py_compile entrypoint.py

# Logic flow test (without Django)
python -c "from entrypoint import wait_for_database; print(wait_for_database('', '5432'))"

# Full test with Docker
docker-compose build web
docker-compose up web
```

### Adding New Functionality
1. Add new functions following the existing pattern
2. Update `main()` to include new steps
3. Test with `python -m py_compile entrypoint.py`
4. Test in Docker container

## Troubleshooting

### Common Issues

#### Database Connection Fails
```bash
# Check environment variables
echo $POSTGRES_HOST $POSTGRES_PORT

# Test connectivity manually
python -c "import socket; sock = socket.socket(); print(sock.connect_ex(('localhost', 5432)))"
```

#### Permission Denied
```bash
# Ensure entrypoint is executable
chmod +x entrypoint.py

# Check Docker build includes chmod
grep -n "chmod.*entrypoint" Dockerfile
```

#### Import Errors
```bash
# Verify Python path
python -c "import sys; print('\n'.join(sys.path))"

# Check Django installation
python -c "import django; print(django.VERSION)"
```

### Debug Mode
Add debug logging to the entrypoint:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Migration from Shell Scripts

If you have existing `entrypoint.sh` files:

1. **Backup**: Save existing shell scripts
2. **Replace**: Use `entrypoint.py` instead
3. **Update Dockerfile**: Change entrypoint reference
4. **Remove Dependencies**: Remove `netcat`, `bash` dependencies
5. **Test**: Verify functionality in target environments

## Security Considerations

- **No shell injection**: Python subprocess module prevents shell injection
- **Environment isolation**: Proper environment variable handling
- **Error disclosure**: Controlled error message disclosure
- **Process management**: Clean process replacement and signal handling

---

**🚀 This Python entrypoint ensures your Django application works consistently across all platforms and environments!**
