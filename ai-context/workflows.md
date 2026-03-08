# Development & Operational Workflows

**Purpose:** This document outlines the standard procedures for setting up the development environment, building features, and running the application.

## 1. Local Development Setup

The entire application is containerized with Docker to ensure a consistent and reproducible environment.

### Prerequisites
- Docker Desktop must be installed and running.

### Environment Configuration
1.  **Create `.env` file:** In the project root, create a file named `.env`.
2.  **Populate `.env`:** Add the following content to the `.env` file. These values are used by `docker-compose.yml` to configure the PostgreSQL database.
    ```
    POSTGRES_DB=stock_db
    POSTGRES_USER=admin
    POSTGRES_PASSWORD=admin
    POSTGRES_HOST=db
    POSTGRES_PORT=5432
    ```

### Running the Application
1.  **Open a terminal** in the project root directory.
2.  **Build and start the services** using Docker Compose. The `-f` flag is necessary if `docker-compose.yml` is not in the root.
    ```bash
    docker-compose -f docker/docker-compose.yml up --build
    ```
    *   `--build`: This flag forces a rebuild of the application's Docker image, which is necessary to include any changes made to the Python code or `requirements.txt`.
3.  **Access the app:** Open a web browser and navigate to `http://localhost:8501`.

## 2. Typical Feature Development Cycle

1.  **Make Code Changes:** Modify the relevant Python files within the `app/` directory.
2.  **Rebuild the Container:** Stop the running application (if it is running) with `Ctrl+C` in the terminal, then run `docker-compose up --build` again to apply the changes.
3.  **Populate Data (First Time Setup):**
    *   Navigate to the **Data** page in the Streamlit UI.
    *   Click the **"Get Data"** button to download the stock data and populate the PostgreSQL database. This step is only needed once, as the database data is persisted in a Docker volume (`postgres_data`).
4.  **Test the Feature:** Navigate to the relevant page (e.g., "Analyze", "Suggestion") and manually test the new functionality.

## 3. Testing Strategy

Currently, testing is performed manually by interacting with the Streamlit UI.

- **DO:** Verify the outputs on each page after making changes.
- **DO:** Check the terminal for any error logs from the Docker containers.
- **DON'T:** Assume a code change works without visually and functionally verifying it in the running application.

## 4. Dependency Management

- **File:** `requirements.txt`
- **Process:**
    1.  To add a new dependency, add it to the `requirements.txt` file.
    2.  Rebuild the Docker image using `docker-compose up --build` to install the new package into the container.

## 5. Stopping the Application

- To stop the running services and remove the containers, run the following command from the project root:
  ```bash
  docker-compose down
  ```
  *This command does **not** delete the database data, which is stored in the `postgres_data` volume.*