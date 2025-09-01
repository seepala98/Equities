# 🚀 Quick Setup Guide (Official Airflow Pattern)

This project follows the [official Apache Airflow Docker Compose pattern](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html).

## First-Time Setup

### 1. Initialize Airflow (Required First Time Only)
```bash
# Initialize Airflow database and create admin user
docker-compose up airflow-init
```

**Expected output:**
```
airflow-init_1       | Upgrades done
airflow-init_1       | Admin user airflow created  
airflow-init_1       | 2.8.1
start_airflow-init_1 exited with code 0
```

### 2. Start All Services
```bash
# Start all services (database, web app, Airflow, pgAdmin)
docker-compose up
```

## Service Access

After startup, access these services:

- **Django Web App**: http://localhost:8000
- **Airflow UI**: http://localhost:8081
  - Username: `admin` 
  - Password: `admin`
- **pgAdmin**: http://localhost:8080
  - Email: `admin@example.com`
  - Password: `admin`

## Services Architecture

The system includes these services:

1. **`db`** - PostgreSQL database
2. **`web`** - Django web application  
3. **`airflow-init`** - Airflow initialization (run once)
4. **`airflow-webserver`** - Airflow web UI
5. **`airflow-scheduler`** - Airflow task scheduler
6. **`pgadmin`** - Database administration UI

## Cleaning Up

To reset everything:
```bash
# Stop all services
docker-compose down

# Remove all data (WARNING: Deletes all data!)
docker-compose down --volumes

# Rebuild from scratch
docker-compose up --build airflow-init
docker-compose up
```

## Key Features

✅ **Official Airflow Pattern** - Follows Apache Airflow documentation  
✅ **Automatic Admin User** - Creates `admin/admin` user automatically  
✅ **Health Checks** - Built-in service health monitoring  
✅ **Separate Services** - Scheduler and webserver run independently  
✅ **Shared Security** - Configured secret key for secure log access
✅ **Cross-Platform** - Works on Windows, Linux, macOS

---

**🎉 Your stock/equities management system with Airflow is ready!**
