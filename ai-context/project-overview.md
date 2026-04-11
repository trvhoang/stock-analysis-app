# Project Overview: Stock Analysis App

## 1. Project Purpose

The Stock Analysis App is a web-based tool designed to analyze historical price movements of stocks on the Vietnamese stock market. Its primary goal is to empower users to identify and validate trading signals based on statistical evidence from past performance. Instead of relying on intuition, users can test hypotheses like, "What typically happens to a stock's price 7 days after it drops by 3% over a 5-day period?"

The application automates the process of:
1.  Downloading and storing historical stock data.
2.  Scanning for user-defined price patterns (signals) across years of data.
3.  Aggregating the outcomes that followed those signals.
4.  Suggesting potential trading opportunities across the market based on these statistical patterns.

## 2. Problem Solved

This application solves the problem of manual, time-consuming, and error-prone backtesting of trading strategies. For a typical investor, validating a simple trading idea would require manually looking through charts, recording data, and performing calculations, which is impractical to do for many stocks or over long time periods.

This tool provides a rapid, data-driven way to answer questions about historical stock behavior, helping users make more informed trading decisions by replacing guesswork with statistics.

## 3. Target Users

The application is built for individual investors, retail traders, and financial analysts who are active in or studying the Vietnamese stock market. These users have a specific trading idea or pattern in mind and need a tool to quickly validate its historical effectiveness.

## 4. Core Functionality & Flow

The application's workflow is divided into distinct pages, each serving a specific purpose.

### Inputs

*   **Data Source:** The app ingests daily stock data (Open, High, Low, Close, Volume) from compressed `.zip` files hosted at an external URL (`cafef1.mediacdn.vn`).
*   **User Parameters:** The user provides analysis criteria, including:
    *   **Ticker:** A specific stock symbol (e.g., `FPT`).
    *   **Validation Day Range:** The number of days over which a "signal" price change occurs.
    *   **Result Day Range:** The number of days after the signal to measure the outcome.

### Outputs

*   **Data Page:** Downloads and populates the database with historical data for a specified number of years.
*   **Result Page:** Displays basic market statistics, such as the top 10 stocks by trading volume and value over a recent period.
*   **Analyze Page:** This page has two tabs:
    1.  **Ticker Analyze:** For a single ticker, it automatically calculates the *current* price delta (the signal) and finds all historical instances of similar events. It outputs a detailed event list, a statistical summary, and predictive advice.
    2.  **Portfolio Analyze:** Allows a user to input a list of tickers and view a summary table of their current signals, historical probabilities, technical trends, and final advice.
*   **Suggestion Page:** Scans the *entire market*, automatically calculating the current price delta for each liquid stock. It then outputs ranked lists of tickers that show the highest historical probability of going up or down following their current, specific signal.
*   **Technical Analyze Page:** Visualize common technical indicators like Moving Averages (MA) and identify key signals such as Golden/Death crosses on interactive charts.

### External API

The application includes a REST API (FastAPI) that allows external systems to consume the analysis logic.
*   **Ticker Analysis:** Provides JSON-formatted statistical and technical advice for any ticker.
*   **Programmatic Control:** Endpoints to trigger data updates and maintenance tasks.
