"""PostgreSQL adapter for the application's fixed, parameterized SQL statements."""
import re
import sqlite3


class PostgresConnection:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.connection = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
        # Cold starts can initialize the schema concurrently.
        self.connection.execute('SELECT pg_advisory_xact_lock(78143218)')

    def execute(self, sql, parameters=()):
        from psycopg.errors import UniqueViolation
        if sql == 'BEGIN IMMEDIATE':
            # Serialize the short count-and-insert transaction across serverless instances.
            return self.connection.execute('SELECT pg_advisory_xact_lock(78143219)')
        sql = re.sub(r"json_extract\(payload, '\$\.(\w+)'\)",
                     lambda match: "(payload::jsonb ->> '" + match[1] + "')", sql)
        sql = sql.replace('?', '%s')
        try:
            return self.connection.execute(sql, parameters)
        except UniqueViolation as exc:
            self.connection.rollback()
            raise sqlite3.IntegrityError('Duplicate record') from exc

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()
