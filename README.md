# PostgreSQL Query AI 🤖

An AI-powered PostgreSQL assistant that converts natural-language questions into SQL queries, executes them against a PostgreSQL database, and helps users understand the results.

## 🚀 Overview

**PostgreSQL Query AI** provides a conversational interface for querying PostgreSQL databases.

Instead of manually writing SQL, users can ask questions such as:

> "Show me the top 10 customers by total spending."

The AI analyzes the database schema, generates an appropriate PostgreSQL query, executes it, and returns the results.

### Workflow

```text
User Question
      ↓
AI / LLM
      ↓
Database Schema
      ↓
SQL Generation
      ↓
SQL Validation
      ↓
PostgreSQL
      ↓
Query Results
      ↓
AI Explanation / Visualization
```

## ✨ Features

- Natural-language database queries
- AI-powered SQL generation
- PostgreSQL schema understanding
- Automatic SQL execution
- Query result formatting
- SQL explanation
- Query error detection
- AI-assisted query correction
- Conversational follow-up questions
- Data analysis using Pandas
- API-based architecture
- Read-only query support for safer database access

## 🧠 How It Works

### 1. User asks a question

```text
What are the top 5 products by revenue?
```

### 2. Schema information is provided to the LLM

The system provides relevant tables, columns, relationships, and data types to the AI.

### 3. SQL is generated

```sql
SELECT product_name,
       SUM(quantity * price) AS revenue
FROM sales
GROUP BY product_name
ORDER BY revenue DESC
LIMIT 5;
```

### 4. Query is executed

The generated SQL is sent to PostgreSQL.

### 5. Results are returned

The application formats the database response into a readable table and can provide an explanation of the result.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| PostgreSQL | Relational database |
| SQL | Database querying |
| LLM | Natural language → SQL |
| FastAPI | Backend API |
| Pandas | Data processing and analysis |
| Git/GitHub | Version control |

## 📁 Suggested Project Structure

```text
postgresql-query-ai/
│
├── app/
│   ├── main.py
│   ├── database.py
│   ├── llm.py
│   ├── query_generator.py
│   ├── query_executor.py
│   └── schema.py
│
├── prompts/
│   └── sql_generation.txt
│
├── tests/
│
├── .env.example
├── requirements.txt
├── .gitignore
└── README.md
```

## ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/<your-username>/postgresql-query-ai.git
cd postgresql-query-ai
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 🔐 Environment Variables

Create a `.env` file:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
LLM_API_KEY=your_api_key
```

Never commit `.env` or API keys to GitHub.

## ▶️ Running the Application

If using FastAPI:

```bash
uvicorn app.main:app --reload
```

The API will be available locally through the configured FastAPI server.

## 💬 Example Queries

The assistant can handle questions such as:

```text
Show all customers from Delhi.
```

```text
What were the total sales last month?
```

```text
Which products have the highest revenue?
```

```text
Show the average order value by customer.
```

```text
How many users signed up this month?
```

```text
Compare monthly revenue for the last 12 months.
```

## 🔒 Security Considerations

Database access should be carefully controlled when allowing AI-generated SQL.

Recommended practices:

- Use a dedicated database user.
- Prefer read-only database permissions.
- Validate generated SQL before execution.
- Restrict destructive commands such as `DROP`, `DELETE`, `UPDATE`, and `TRUNCATE`.
- Never expose database credentials to the frontend.
- Store credentials in environment variables.
- Implement query timeouts.
- Log generated queries for debugging and auditing.

## 🔮 Future Improvements

- RAG-based schema retrieval for large databases
- Automatic chart generation
- Multi-database support
- SQL query history
- Query caching
- User authentication
- Role-based database permissions
- Streaming AI responses
- Advanced data visualization
- Query performance optimization
- AI-generated database insights
- Voice-based database querying
- Support for multiple SQL dialects

## 🎯 Use Cases

PostgreSQL Query AI can be useful for:

- Data analysts
- Developers
- Business teams
- Product managers
- Database administrators
- BI applications
- Internal analytics tools
- AI-powered data platforms

## 📌 Project Objective

The project demonstrates how **Generative AI, SQL, PostgreSQL, and backend APIs** can be combined to build a natural-language data-access layer.

The long-term vision is to transform a traditional database interface into an **AI-powered conversational analytics system**.

## 📄 License

This project is available under the license specified in the repository.
