import re
import subprocess
import time
import unittest
from pathlib import Path

import requests


class Test(unittest.TestCase):
    api_exporter = None
    mock_api = None

    @classmethod
    def setUpClass(cls):
        # Launching the exporter
        if not cls.api_exporter:
            cls.api_exporter = subprocess.Popen(
                ['python3', '../meraki_api_exporter.py', '-k', 'nope', '-i', '127.0.0.1', '-m',
                 'http://127.0.0.1:9823/api/v1'])

        # Launching the mock dashboard API app
        if not cls.mock_api:
            cls.mock_api = subprocess.Popen(
                ['python3', '../mock_api/mock_api.py'])

        # HACK: Wait for the server to be launched
        while True:
            try:
                requests.get("http://127.0.0.1:9822/", timeout=0.5)
                requests.get("http://127.0.0.1:9823/", timeout=0.5)
                break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.api_exporter.terminate()
        cls.mock_api.terminate()

    def test_get_organizations(self):
        response = requests.get('http://127.0.0.1:9822/organizations')
        self.assertEqual(response.text, '- targets:\n   - 1234\n')

    def test_get_metrics(self):
        response = requests.get('http://127.0.0.1:9822/?target=1234')
        response_sanitised = re.sub(r"request_processing_seconds [\d]+.[\d]+", "request_processing_seconds 0.01",
                                    response.text)
        expected_response = Path('integration_text_response.txt').read_text()
        self.assertEqual(response_sanitised, expected_response)
