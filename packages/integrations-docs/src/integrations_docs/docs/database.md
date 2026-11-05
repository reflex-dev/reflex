---
tags: Data Infrastructure
description: Connect Reflex Build apps to PostgreSQL, MySQL, MSSQL, or SQLite databases.
---
# Database Integration

The Database Integration connects Reflex Build apps to an existing SQL database. When you enable the connection for an app, Reflex Build can inspect its schema and use that structure while generating the app.

## Supported Databases

- **PostgreSQL**
- **MySQL**
- **MSSQL** (Microsoft SQL Server)
- **SQLite**

## Add a Database Integration

1. Open **Integrations** from the project sidebar.
2. Select **Add integration**.
3. Search for and select **Database**.
4. Configure the connection using **Connection Details** or **Database URI**.
5. Optionally enter an integration name to distinguish this connection from others in the project.
6. Select **Connect**. When you edit an existing connection later, the button reads **Save Changes**.

The integration is saved at the project level. Open an app's **Integrations** panel to enable it for that app when needed.

## Connection Details

Use **Connection Details** to enter each part of the connection separately.

For PostgreSQL, MySQL, and MSSQL, choose the database type and enter:

- `hostname`: the database server address.
- `port`: defaults to `5432` for PostgreSQL, `3306` for MySQL, or `1433` for MSSQL.
- `username` and `password`: the database credentials.
- `database_name`: the database to connect to.

For MSSQL, **Trust Server Certificate** skips certificate identity validation. Use it only as a temporary workaround for an untrusted or self-signed server certificate, and prefer configuring a certificate that the client trusts.

For SQLite, select **SQLite** and enter an HTTP or HTTPS **SQLite Download URL**. Reflex Build downloads the database file before using it.

## Database URI

Use **Database URI** when you have a complete connection URI for one of the supported database types. For example:

```text
postgresql://username:password@hostname:5432/database_name
```

Enter the URI in `db_url`, then select **Connect**. Reflex Build selects the database driver automatically. Include provider-required connection options as query parameters when needed.

## Connect through an SSH Tunnel

Use an SSH tunnel when the database is on a private network but can be reached through a bastion host. This option is available for PostgreSQL, MySQL, and MSSQL in both connection modes. It is not available for SQLite.

1. Enter the database connection details or URI. Keep the database hostname and port set to the address the bastion host uses to reach the database.
2. Turn on **Connect via SSH tunnel**.
3. Enter the `ssh_hostname`, `ssh_port` (usually `22`), and `ssh_username` for the bastion host.
4. Paste the corresponding **SSH private key**, starting with its `-----BEGIN` line.
5. Select **Connect**.

The SSH account must allow port forwarding to the database host and port. Use a dedicated, restricted SSH key and database user for Reflex Build.

```md alert warning
# Keep credentials private

Enter database passwords, connection URIs, and SSH private keys only in the integration form. Do not put them in prompts, knowledge, source code, or screenshots.
```

## Use TLS Certificates

For PostgreSQL and MSSQL, turn on **Use TLS certificates** when the server needs a certificate the sandbox does not trust by default, or requires client certificates. It is available in both connection modes.

- **CA / server certificate**: the PEM certificate that signs the server's certificate.
- **Server verification** (PostgreSQL only): `default` follows an `sslmode` in the connection URI, otherwise `verify-full` when a CA is set. `verify-full` also checks the server hostname; `verify-ca` checks only the certificate chain.
- **Client certificate** and **Client private key** (PostgreSQL only): for servers that require mutual TLS.

## Managed Postgres

If you don't have a database, select **Provision database** on the Database card to have Reflex Build create a managed Postgres database for the app. While an app uses a managed database, the Database card shows a notice instead of the connection form; manage the database, or delete it to connect your own, from the **Database** tab.

## Enable the Integration for an App

Open the app's **Integrations** panel and enable the saved database connection. Reflex Build then connects to the database and, when the app does not already have a model file, creates the app's data models from the schema.

If the connection fails, check that:

- The database or bastion host is reachable.
- The ports are open and the credentials are valid.
- The database user can read the schema and has only the data permissions the app needs.
- The SSH user can forward traffic to the database when tunneling is enabled.
- The database hostname resolves to an IPv4 address. The sandbox has no IPv6, so a "Network is unreachable" error usually means an IPv6-only host; use the provider's IPv4 or connection-pooler address instead, such as Supabase's pooler connection string.

```md alert
# NoSQL Databases

Use the dedicated MongoDB integration when applicable. For another NoSQL database, add its Python SDK or configure a custom integration; the Database Integration supports SQL databases.
```
