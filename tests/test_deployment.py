import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


class DeploymentTests(unittest.TestCase):
    def load_vercel(self, **settings):
        env = {'VERCEL': '1', 'SECRET_KEY': '', 'DATABASE_URL': '', 'POSTGRES_URL': '', **settings}
        with patch.dict(os.environ, env), patch('dotenv.load_dotenv'), patch('pathlib.Path.mkdir') as mkdir:
            module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'app.py'))
            mkdir.assert_not_called()
        return module['app'].test_client()

    def test_missing_settings_show_setup_instead_of_crashing(self):
        client = self.load_vercel()
        response = client.get('/')
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'DATABASE_URL', response.data)
        self.assertIn(b'SECRET_KEY', response.data)
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertEqual(client.post('/api/records', json={}).status_code, 503)

    def test_database_missing_does_not_fall_back_to_sqlite(self):
        client = self.load_vercel(SECRET_KEY='test-secret')
        self.assertEqual(client.get('/api/session').json['error'], 'Sunucu kurulumu eksik: DATABASE_URL')

    def test_configured_vercel_can_render_without_database_connection(self):
        client = self.load_vercel(SECRET_KEY='test-secret', DATABASE_URL='postgresql://example.invalid/test')
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Secure', response.headers['Set-Cookie'])
