---
tags: Data Infrastructure
description: Connect to SQL or NoSQL databases to query, store, and manage structured data.
---
# Database Integration

The Database Integration allows you to connect your AI-generated applications to real databases, automatically generating schemas and enabling data-driven functionality.

## Supported Databases

- **PostgreSQL** - Recommended for production applications
- **MySQL** - Popular open-source database
- **SQLite** - Lightweight database, perfect for development and small applications
- **MSSQL** - Microsoft SQL Server support

## Getting Started

### Opening the Database Integration

1. Navigate to your app in the AI Builder
2. Open the **Settings drawer** (gear icon)
3. Click on the **Integrations** tab
4. Find and enable the **Database** integration

### Connection Methods

The Database Integration offers two convenient ways to connect:

#### 1. Connection Details (Recommended)

This user-friendly form breaks down your database connection into individual fields:

**For PostgreSQL, MySQL and MSSQL:**
- **Database Type**: Select from dropdown (PostgreSQL/MySQL/MSSQL)
- **Hostname**: Your database server address (e.g., `localhost`, `db.company.com`)
- **Port**: Automatically filled (PostgreSQL: 5432, MySQL: 3306, MSSQL: 1433) or specify custom port
- **Username**: Your database username
- **Password**: Your database password (securely handled)
- **Database Name**: The specific database to connect to

**For SQLite:**
- **Database Type**: Select "SQLite" from dropdown
- **SQLite Download URL**: Either a local file path or HTTP URL to download the database file

#### 2. Database URI

For advanced users who prefer the traditional connection string format:

**PostgreSQL:**
```
postgresql://username:password@hostname:port/database_name
```

**MySQL:**
```
mysql://username:password@hostname:port/database_name
```

**MSSQL:**
```
mssql://username:password@hostname:port/database_name
```

**SQLite:**
```
sqlite:///path/to/database.sqlite
sqlite+https://example.com/database.sqlite
```

## Database URI Components

Protocol (postgresql://) - Database type identifier
Username (admin) - Database user credentials
Password (secret123) - User password (kept secure)
Hostname (db.company.com) - Server address
Port (5432) - Connection port
Database (mydatabase) - Target database name

## Connection Process

1. **Choose your method**: Use either Connection Details form or Database URI
2. **Fill in credentials**: Provide your database connection information
3. **Click Connect**: The system will validate and test your connection
4. **Schema Generation**: Upon successful connection, the system automatically:
   - Connects to your database
   - Analyzes the database structure
   - Generates SQLAlchemy models
   - Makes schema available to the AI for queries


```md alert
# NoSQL Databases

NoSQL databases (e.g., MongoDB, DynamoDB) can be accessed via Python SDKs which the AI Builder can install if you prompt for it. The first class Database integration currently supports only SQL databases.
```