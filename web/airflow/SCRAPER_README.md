Building and using the scraper image

This project now includes a small scraper image used by the Airflow DAG.

To build the scraper image locally:

    cd "C:\Users\vardhan\github_clones\Investment Portfolio"
    docker compose build scraper

If the image builds successfully it will be tagged as `investmentportfolio_scraper:latest` and
Airflow's DockerOperator will be able to run it.

To test the image locally (runs the management command inside the container):

    docker compose run --rm scraper python manage.py scrape_tsx_listings --exchange=TSX --letters A

Notes:
- The scraper image reuses the project's `requirements.txt` and copies only the minimal files needed.
- The Airflow DAG `tsx_listing_scraper` is configured to use the `investmentportfolio_scraper:latest` image.

Airflow notes about concurrency and DockerOperator

- The DAG uses TaskGroups and runs one DockerOperator task per letter per exchange in parallel. Adjust `max_active_tasks` and `concurrency` in the DAG definition to control parallelism.
- DockerOperator requires that the Airflow worker can talk to the Docker daemon. If Airflow runs in a container, make sure the container image includes the Docker SDK/provider (`apache-airflow-providers-docker`) and has access to the Docker daemon (socket or remote Docker host).
- If you can't or don't want to expose the Docker socket, consider running Airflow on the host or using KubernetesPodOperator instead.

Tuning tips

- Start with low concurrency (e.g., 4) and increase after observing DB and network load.
- Add rate-limiting or sleeps to the management command if you see remote site throttling.
