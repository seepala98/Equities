Airflow DAGs for TSX listing scraper

This folder contains a simple Airflow DAG that runs the Django management command
`scrape_tsx_listings` inside the repo's `web` service via `docker-compose run`.

Requirements / notes:
- Docker and docker-compose must be available on the host where Airflow runs.
- The Airflow container needs access to the Docker socket so it can invoke `docker-compose`.
  We mount `/var/run/docker.sock` into the container in the root `docker-compose.yml`.
- The DAG calls: `docker-compose run --rm web python manage.py scrape_tsx_listings --exchange=both`.

How to run (host):

1. Start the stack:

   docker-compose up -d

2. Open the Airflow UI at http://localhost:8081 and enable the DAG `tsx_listing_scraper`.

3. Run the DAG manually or wait for the daily schedule.

Security:
- Mounting the Docker socket into containers grants them elevated control over the host Docker daemon.
  Only do this in trusted environments.

Alternative:
- If you prefer not to expose the socket, run the scraper using an Airflow KubernetesPodOperator or
  implement the scraping logic as a standalone Docker image the DAG can run directly.
