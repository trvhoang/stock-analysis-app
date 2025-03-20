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

   HOW TO RUN
   Install and start Docker app (Installation https://docs.docker.com/desktop/setup/install/windows-install/)

   Build and run the app: 
   docker-compose -f docker/docker-compose.yml up --build

   Stop running app (if error duplicated data or any loading data issue)
   docker-compose -f docker/docker-compose.yml down


   HOW TO USE:
   Data Page: 
   - Up to data day: default is today
   - Validation year range: default is 10 years

   Result Page:
   - Select month range: default is 3 months
   - Top 10 code by trading volume
   - Top 10 code by trading value (price * volume)

   Analyze Page:
   - Input data to validate a specific signal:
      . Stock code
      . Signal: validation day range, detal range. 
      . Result day range: day range price after signal
         For example: code = FPT, validation day range = 3, detal range = -10, result day range = 7
            Find all time in history when FPT has 3 cumulative day with -10% price (close price of day T+3 compare to close price of day T)
               and capture the price change of the next 7 cumulative day after the signal happen