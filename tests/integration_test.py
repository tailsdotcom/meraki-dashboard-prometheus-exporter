import subprocess
import time
import unittest

import requests
from prometheus_client.openmetrics import parser


class Test(unittest.TestCase):
    api_exporter = None
    mock_api = None

    @classmethod
    def setUpClass(cls):
        # Launching the exporter
        if not cls.api_exporter:
            cls.api_exporter = subprocess.Popen(
                [
                    "python3",
                    "../meraki_api_exporter.py",
                    "-k",
                    "nope",
                    "-i",
                    "127.0.0.1",
                    "-m",
                    "http://127.0.0.1:9823/api/v1",
                    "-o",
                    "1234"
                ]
            )

        # Launching the mock dashboard API app
        if not cls.mock_api:
            cls.mock_api = subprocess.Popen(["python3", "../mock_api/mock_api.py"])

        # HACK: Wait for the server to be launched
        while True:
            try:
                requests.get("http://127.0.0.1:9822/", timeout=0.5)
                requests.get("http://127.0.0.1:9823/", timeout=0.5)
                time.sleep(5)  # Give it a few more seconds for luck
                break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.api_exporter.terminate()
        cls.mock_api.terminate()

    def test_get_metrics(self):
        response = requests.get(
            "http://127.0.0.1:9822/",
            headers={"accept": "application/openmetrics-text"},
        )

        if_count = 0
        # Validate against OpenMetrics Spec and check all expected metrics are present and correct
        for family in parser.text_string_to_metric_families(response.text):
            for sample in family.samples:
                if sample[0] == "meraki_device_uplink_latency":
                    self.assertEqual(sample[1]["deviceName"], "My AP")
                    self.assertEqual(sample[1]["networkId"], "N_24329156")
                    self.assertEqual(sample[1]["networkName"], "My network")
                    self.assertEqual(sample[1]["serial"], "Q234-ABCD-5678")
                    if sample[1]["uplink"] == "wan1":
                        self.assertEqual(sample[2], 0.19490000000000002)
                        if_count += 1
                    elif sample[1]["uplink"] == "cellular":
                        self.assertEqual(sample[2], 0.2555)
                        if_count += 1

                elif sample[0] == "meraki_device_uplink_loss":
                    self.assertEqual(sample[1]["deviceName"], "My AP")
                    self.assertEqual(sample[1]["networkId"], "N_24329156")
                    self.assertEqual(sample[1]["networkName"], "My network")
                    self.assertEqual(sample[1]["serial"], "Q234-ABCD-5678")
                    if sample[1]["uplink"] == "wan1":
                        self.assertEqual(sample[2], 5.3)
                        if_count += 1
                    elif sample[1]["uplink"] == "cellular":
                        self.assertEqual(sample[2], 1.2)
                        if_count += 1

                elif sample[0] == "meraki_device_status":
                    self.assertEqual(sample[1]["deviceName"], "My AP")
                    self.assertEqual(sample[1]["networkId"], "N_24329156")
                    self.assertEqual(sample[1]["networkName"], "My network")
                    self.assertEqual(sample[1]["serial"], "Q234-ABCD-5678")
                    self.assertEqual(sample[2], 1)
                    if_count += 1

                elif sample[0] == "meraki_device_using_cellular_failover":
                    self.assertEqual(sample[1]["deviceName"], "My AP")
                    self.assertEqual(sample[1]["networkId"], "N_24329156")
                    self.assertEqual(sample[1]["networkName"], "My network")
                    self.assertEqual(sample[1]["serial"], "Q234-ABCD-5678")
                    self.assertEqual(sample[2], 0)
                    if_count += 1

                elif sample[0] == "meraki_device_uplink_status":
                    self.assertEqual(sample[1]["deviceName"], "My AP")
                    self.assertEqual(sample[1]["networkId"], "N_24329156")
                    self.assertEqual(sample[1]["networkName"], "My network")
                    self.assertEqual(sample[1]["serial"], "Q234-ABCD-5678")

                    if sample[1]["uplink"] == "wan1":
                        self.assertEqual(sample[2], 0)
                        if_count += 1
                    elif sample[1]["uplink"] == "cellular":
                        self.assertEqual(sample[2], 1)
                        if_count += 1

                elif sample[0] == "meraki_network_uplink_sent":
                    self.assertEqual(sample[1]["networkId"], "N_24329156")
                    self.assertEqual(sample[1]["networkName"], "My network")
                    if sample[1]["uplink"] == "wan1":
                        self.assertEqual(sample[2], 1111)
                        if_count += 1
                    elif sample[1]["uplink"] == "cellular":
                        self.assertEqual(sample[2], 3333)
                        if_count += 1

                elif sample[0] == "meraki_network_uplink_received":
                    self.assertEqual(sample[1]["networkId"], "N_24329156")
                    self.assertEqual(sample[1]["networkName"], "My network")
                    if sample[1]["uplink"] == "wan1":
                        self.assertEqual(sample[2], 2222)
                        if_count += 1
                    elif sample[1]["uplink"] == "cellular":
                        self.assertEqual(sample[2], 4444)
                        if_count += 1

        # Check all conditional paths are explored
        self.assertEqual(if_count, 12)
