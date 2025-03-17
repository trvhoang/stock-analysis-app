# Stock Analysis App

A Python-based web application built with Streamlit to download and analyze stock trading data from CSV files within a ZIP archive. The app uses PostgreSQL for data storage and is containerized with Docker and Docker Compose.

## Prerequisites
- Docker
- Docker Compose

## Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd stock-analysis-app

   Access the app at http://localhost:8501

   Build and run the app: 
   docker-compose -f docker/docker-compose.yml up --build

   Stop running app
   docker-compose -f docker/docker-compose.yml down