This workspace contains a Docker Compose setup for a Django app that stores stock data in Postgres and uses Selenium for scraping.

Services:
- db: Postgres 15
- pgadmin: PgAdmin 4 on port 8080
- web: Django app on port 8000 (includes Selenium + Firefox + Geckodriver)

Quick start (Windows PowerShell):

# From the repository root
docker compose up --build

Then open http://localhost:8000 and pgAdmin at http://localhost:8080 (login: admin@local.test / admin).

Notes:
- The Django app will auto-run migrations on startup. Create a superuser with `docker compose exec web python manage.py createsuperuser` if needed.
- For scraping with Selenium, the container ships Firefox and Geckodriver; use Selenium's Firefox WebDriver in your code.
