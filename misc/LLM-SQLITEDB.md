# 📊 Advanced Reporting with Local LLM + SQLite

## 🧠 Overview

This guide teaches you how to use a **local LLM** to generate **advanced SQL queries for reporting** using a SQLite database.

You will learn how to:
- Translate natural language into SQL
- Handle complex reporting queries (aggregations, joins, filters)
- Improve accuracy and prevent errors
- Build a structured reporting pipeline

---

## 🏗️ Architecture


User Question
↓
Local LLM
↓
Prompt + Schema Context
↓
SQL Query Generation
↓
SQLite Execution
↓
Result Processing
↓
LLM Explanation (Optional)


---

## 🧰 Requirements

Install dependencies:

```bash
uv add langchain sqlite-utils pandas

## Example Schema
employees (
    id INTEGER,
    name TEXT,
    department TEXT,
    salary INTEGER
)

departments (
    id INTEGER,
    name TEXT
)

sales (
    id INTEGER,
    employee_id INTEGER,
    amount INTEGER,
    date TEXT
)


## Step 1: Connect to SQLite

from langchain.utilities import SQLDatabase

db = SQLDatabase.from_uri("sqlite:///company.db")

## Step 2: Load Local LLM
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8888/v1",  # your local LLM server
    api_key=1234,                   # usually ignored
    model=""Qwen3.5-9B-MLX-4bit"              # depends on your local model name
)

## Use Langchain SQL Agent

from langchain.utilities import SQLDatabase
from langchain.agents import create_sql_agent
from langchain.agents.agent_types import AgentType
from langchain.chat_models import ChatOpenAI

# Connect DB
db = SQLDatabase.from_uri("sqlite:///company.db")

# Connect to local LLM
llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed",
    model="your-local-model",
    temperature=0
)

# Create agent
agent = create_sql_agent(
    llm=llm,
    db=db,
    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Ask question
response = agent.run("Show total sales per department")
print(response)


## Advance Prompting

from langchain.schema import SystemMessage, HumanMessage

messages = [
    SystemMessage(content="""
    You are a senior SQL analyst.
    Only generate valid SQLite queries.
    Never hallucinate columns.
    """),
    HumanMessage(content="Top 5 employees by sales")
]

response = llm(messages)
print(response.content)


## Safety layer

def is_safe(query):
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT"]
    return not any(word in query.upper() for word in forbidden)
    
add strict prompts
- Only SELECT queries allowed
- No data modification
- No schema changes

## 🚀 Pro Setup (Best Practice)

If you're building something serious:

Use this stack:
LLM → OpenAI-compatible server
Orchestration → LangChain
DB → SQLite / PostgreSQL
Backend → Flask


## ⚠️ Common Issues
1. Model ignores instructions

Fix:

Lower temperature (temperature=0)
Use stronger system prompts
2. Wrong SQL syntax

Fix:

Add: "Use SQLite syntax only"
3. Hallucinated joins

Fix:

Provide schema + relationships clearly


## 1. Prerequisites
You’ll need langchain, langchain-community, and langchain-openai (or your provider of choice). Since SQLite is built into Python, you don't need to install a separate database engine.

Bash
pip install langchain langchain-community langchain-openai
2. Connect to the Database
LangChain uses SQLAlchemy under the hood to handle database connections. You define the connection string using the standard SQLite format.

Python
from langchain_community.utilities import SQLDatabase

# Use a local file (e.g., 'my_data.db') or an in-memory database
db = SQLDatabase.from_uri("sqlite:///example.db")

# Verify connection
print(db.dialect)
print(db.get_usable_table_names())
3. Using the SQL Agent
The most robust way to interact with the DB is through a SQL Agent. It can look at your schema, decide which tables to query, and handle errors if the first SQL query fails.

Python
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Create the agent executor
agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)

# Ask a question
response = agent_executor.invoke({"input": "How many users are in the customers table?"})
print(response["output"])
