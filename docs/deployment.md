# Future private deployment

Deployment is out of scope. Before company access: confirm data rights, add company-approved identity/access control, TLS, secret management, database backups and restore tests, dependency/security monitoring, audit logging and refresh alerts. Move SQLite to tested PostgreSQL and the local refresh worker to a durable scheduled worker with cross-process leases. Validate concurrency, retention, point-in-time data and recovery. Do not expose the current unauthenticated Streamlit app as production-secure.
