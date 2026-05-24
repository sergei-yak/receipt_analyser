AI Financial Intelligence Assistant

A multi-agent AI system built with LangGraph, OpenAI, and Telegram Bot API that can:

Parse receipts/checks from images
Extract structured financial data
Store user-specific spending history
Prevent duplicate uploads
Answer natural language spending questions
Generate charts and visualizations on demand
Features
Receipt & Check Processing

Users can upload:

Receipt photos
Check images
Screenshot receipts
Telegram image documents

The system extracts:

Date
Merchant
Amount
Category
Memo/description

Example:

Saved transaction:
Date: 2026-05-24
Merchant: Walmart
Amount: $45.72
Category: groceries
Duplicate Detection

The system calculates an MD5 hash for every uploaded image.

If the same receipt/check is uploaded again:

Duplicate skipped. You already uploaded this receipt/check.
User-Specific Financial Memory

Each Telegram user has a separate dataset:

user_data/user_<telegram_user_id>_spending.xlsx

This allows persistent financial memory between Telegram conversations.

Natural Language Financial Questions

Users can ask:

How much did I spend on water last month?
What was my last purchase?
How much did I spend on restaurants?
Which merchant did I spend the most money at?
AI Chart Generation

Users can request charts directly in Telegram.

Examples:

Show all historical transactions
Show cumulative spending over time
Show spending by category
Show spending by merchant
Show distribution of transaction amounts

Supported chart types:

Bar charts
Line charts
Pie charts
Histograms
Multi-Agent Architecture
User Message
      ↓
Router Agent
 ┌───────────────┬────────────────┬─────────────────┐
 ↓               ↓                ↓
Receipt Path     Analytics Path   Plot Path
 ↓               ↓                ↓
Vision Parser    Analytics Agent  Plot Planner Agent
 ↓                                ↓
Validation Agent                 Chart Renderer Agent
 ↓
Storage Agent
Agents
Router Agent

Determines user intent:

receipt upload
analytics question
plotting request
Vision Parser Agent

Uses OpenAI Vision model to extract structured financial information from receipt/check images.

Validation Agent

Checks extracted fields:

validates amount
fills missing categories
prevents bad records
Storage Agent

Stores transactions into user-specific Excel datasets.

Also handles duplicate detection using file hashes.

Analytics Agent

Answers natural language financial questions using the user's stored dataset.

Plot Planner Agent

Converts user requests into a safe structured plotting plan.

Example:

{
    "chart_type": "pie",
    "group_by": "category",
    "aggregation": "sum"
}
Chart Renderer Agent

Creates charts using matplotlib based on the generated plot plan.

Project Structure
project/
│
├── check_spending_agent.py
├── telegram_bot.py
├── .env
│
├── user_data/
├── downloads/
├── plots/
│
└── README.md
Installation
1. Clone repository
git clone <your_repo_url>
cd <your_project>
2. Install dependencies

Using uv:

uv add langgraph langchain-openai python-telegram-bot pandas openpyxl python-dotenv matplotlib pydantic

Or using pip:

pip install langgraph langchain-openai python-telegram-bot pandas openpyxl python-dotenv matplotlib pydantic
Environment Variables

Create .env file:

OPENAI_API_KEY=your_openai_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
Running the Bot
python telegram_bot.py
Example Telegram Usage
Upload Receipt

Send:

photo
screenshot
receipt image

Bot response:

Saved transaction:
Date: 2026-05-24
Merchant: Costco
Amount: $82.17
Category: groceries
Ask Questions
How much did I spend on groceries?
What was my last purchase?
Generate Charts
Show spending by category
Show cumulative spending over time

Bot generates and sends chart image.

Technologies Used
Python
LangGraph
LangChain
OpenAI Vision
Telegram Bot API
Pandas
Matplotlib
Pydantic
Excel (.xlsx) storage
Future Improvements
Database Support

Replace Excel with:

PostgreSQL
SQLite
DuckDB
Forecasting Agent

Add:

ARIMA
Prophet
LSTM forecasting

Examples:

Predict next month's grocery spending
Fraud Detection Agent

Detect:

unusual transactions
abnormal spending spikes
duplicate charges
RAG Financial Search

Search historical receipts semantically:

Find the receipt where I bought tires
Voice Assistant

Telegram voice messages:

How much did I spend on gas this month?
Dashboard Integration
Plotly dashboards
Power BI integration
Automated PDF reports
Security Notes
Each Telegram user has isolated datasets.
Duplicate uploads are prevented using MD5 file hashes.
No raw plotting code is executed from LLM outputs.
Plot generation uses validated structured plans.
License

MIT License