import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from psycopg.errors import UniqueViolation
from storage import PostgresConnection


class StorageTests(unittest.TestCase):
    def test_json_filter_and_parameter_binding(self):
        with patch('psycopg.connect') as connect:
            store = PostgresConnection('postgresql://test')
            store.execute("SELECT * FROM records WHERE owner=? AND json_extract(payload, '$.kind')='daily'", ('owner',))
            connect.return_value.execute.assert_called_with(
                "SELECT * FROM records WHERE owner=%s AND (payload::jsonb ->> 'kind')='daily'", ('owner',))

    def test_transaction_lock_and_duplicate_rollback(self):
        with patch('psycopg.connect') as connect:
            store = PostgresConnection('postgresql://test')
            store.execute('BEGIN IMMEDIATE')
            connect.return_value.execute.assert_called_with('SELECT pg_advisory_xact_lock(78143219)')
            connect.return_value.execute.side_effect = UniqueViolation('duplicate')
            with self.assertRaises(sqlite3.IntegrityError):
                store.execute('INSERT INTO records VALUES (?)', ('id',))
            connect.return_value.rollback.assert_called_once()
