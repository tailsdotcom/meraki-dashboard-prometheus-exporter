import logging
import time

import configargparse
import meraki
from prometheus_client import Gauge, start_http_server


def get_networks(network_devices_dict, dashboard, organization_id):
    try:
        networks = dashboard.organizations.getOrganizationNetworks(
            organizationId=organization_id, total_pages="all"
        )
        for network in networks:
            network_id = network["id"]
            if network_id not in network_devices_dict:
                network_devices_dict[network_id] = {}
            network_devices_dict[network_id] = network
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_devices(network_devices_dict, dashboard, organization_id):
    try:
        devices_statuses = dashboard.organizations.getOrganizationDevicesStatuses(
            organizationId=organization_id, total_pages="all"
        )
        logging.info(f"Got {len(devices_statuses)} Devices")

        for device in devices_statuses:
            network_id = device["networkId"]
            serial = device["serial"]
            if network_id not in network_devices_dict:
                network_devices_dict[network_id] = {}
            if "devices" not in network_devices_dict[network_id]:
                network_devices_dict[network_id]["devices"] = {}
            network_devices_dict[network_id]["devices"][serial] = device
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_uplinks_loss_and_latency(network_devices_dict, dashboard, organization_id):
    try:
        uplink_loss_and_latency = (
            dashboard.organizations.getOrganizationDevicesUplinksLossAndLatency(
                organizationId=organization_id,
                ip="8.8.8.8",
                timespan="120",
                total_pages="all",
            )
        )

        logging.info(f"Got {len(uplink_loss_and_latency)} Device Statuses")

        for uplink in uplink_loss_and_latency:
            network_id = uplink["networkId"]
            serial = uplink["serial"]
            uplink_name = uplink["uplink"]
            if network_id in network_devices_dict:
                if serial in network_devices_dict[network_id]["devices"]:
                    if (
                        "uplinks"
                        not in network_devices_dict[network_id]["devices"][serial]
                    ):
                        network_devices_dict[network_id]["devices"][serial][
                            "uplinks"
                        ] = {}

                    latency_metric = uplink["timeSeries"][-1]["latencyMs"]
                    if latency_metric:
                        latency_metric = latency_metric / 1000

                    network_devices_dict[network_id]["devices"][serial]["uplinks"][
                        uplink_name
                    ] = {
                        "latency": latency_metric,
                        "loss": uplink["timeSeries"][-1]["lossPercent"],
                    }
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_uplink_statuses(network_devices_dict, dashboard, organization_id):
    try:
        uplink_statuses = dashboard.appliance.getOrganizationApplianceUplinkStatuses(
            organizationId=organization_id, total_pages="all"
        )
        logging.info(f"Got {len(uplink_statuses)} Uplink Statuses")

        for device in uplink_statuses:
            network_id = device["networkId"]
            serial = device["serial"]
            if network_id in network_devices_dict:
                if serial in network_devices_dict[network_id]["devices"]:
                    if (
                        "uplinks"
                        not in network_devices_dict[network_id]["devices"][serial]
                    ):
                        network_devices_dict[network_id]["devices"][serial][
                            "uplinks"
                        ] = {}
                    for uplink in device["uplinks"]:
                        uplink_name = uplink["interface"]
                        if (
                            uplink_name
                            not in network_devices_dict[network_id]["devices"][serial][
                                "uplinks"
                            ]
                        ):
                            network_devices_dict[network_id]["devices"][serial][
                                "uplinks"
                            ][uplink_name] = {}
                        network_devices_dict[network_id]["devices"][serial]["uplinks"][
                            uplink_name
                        ]["status"] = uplink["status"]
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_uplink_usage(network_devices_dict, dashboard):
    for network_id in network_devices_dict.keys():
        try:
            uplink_usage_list = (
                dashboard.appliance.getNetworkApplianceUplinksUsageHistory(
                    networkId=network_id
                )
            )
            if "interfaces" not in network_devices_dict[network_id]:
                network_devices_dict[network_id]["interfaces"] = {}

            interface_dict = uplink_usage_list[-1]["byInterface"]
            for interface in interface_dict:
                network_devices_dict[network_id]["interfaces"][
                    interface["interface"]
                ] = {"sent": interface["sent"], "received": interface["received"]}
            logging.info(
                f"Got {len(interface_dict)} Uplink Usages for network {network_id}"
            )
        except meraki.APIError as api_error:
            logging.warning(api_error)


def get_usage(dashboard, organization_id):
    network_devices_dict = {}
    get_networks(network_devices_dict, dashboard, organization_id)
    get_devices(network_devices_dict, dashboard, organization_id)
    get_uplinks_loss_and_latency(network_devices_dict, dashboard, organization_id)
    get_uplink_statuses(network_devices_dict, dashboard, organization_id)
    get_uplink_usage(network_devices_dict, dashboard)

    return network_devices_dict


REQUEST_TIME = Gauge("request_processing_seconds", "Time spent processing request")
label_list = ["networkId", "networkName"]
network_uplink_sent_metric = Gauge(
    "meraki_network_uplink_sent",
    "Network Uplink Sent Bytes (per minute)",
    label_list + ["uplink"],
)
network_uplink_received_metric = Gauge(
    "meraki_network_uplink_received",
    "Network Uplink Received Bytes (per minute)",
    label_list + ["uplink"],
)
device_status_metric = Gauge(
    "meraki_device_status", "Device Status", label_list + ["serial", "deviceName"]
)
device_cellular_failover_metric = Gauge(
    "meraki_device_using_cellular_failover",
    "Cellular Failover",
    label_list + ["serial", "deviceName"],
)
device_uplink_latency_metric = Gauge(
    "meraki_device_uplink_latency",
    "Device Uplink Latency (seconds)",
    label_list + ["serial", "deviceName", "uplink"],
)
device_uplink_loss_metric = Gauge(
    "meraki_device_uplink_loss",
    "Device Uplink Loss (percent)",
    label_list + ["serial", "deviceName", "uplink"],
)

device_uplink_status_metric = Gauge(
    "meraki_device_uplink_status",
    "Device Uplink Status",
    label_list + ["serial", "deviceName", "uplink"],
)


@REQUEST_TIME.time()
def update_metrics():
    dashboard = meraki.DashboardAPI(API_KEY, base_url=API_URL, suppress_logging=True)
    organization_id = ORG_ID

    network_devices_dict = get_usage(dashboard, organization_id)
    logging.info(f"Reporting on: {len(network_devices_dict)} networks")

    # uplink statuses
    uplink_status_mappings = {
        "active": 0,
        "ready": 1,
        "connecting": 2,
        "not connected": 3,
        "failed": 4,
    }

    for network_id, network_details in network_devices_dict.items():
        network_name = network_details["name"]
        if "interfaces" in network_details:
            for uplink_name, uplink_details in network_details["interfaces"].items():
                network_uplink_sent_metric.labels(
                    network_id, network_name, uplink_name
                ).set(uplink_details["sent"])
                network_uplink_received_metric.labels(
                    network_id, network_name, uplink_name
                ).set(uplink_details["received"])

        if "devices" in network_details:
            for device_serial, device_details in network_details["devices"].items():
                if "name" in device_details and device_details["name"]:
                    device_name = device_details["name"]
                else:
                    device_name = device_details["mac"]

                if "status" in device_details:
                    device_status_metric.labels(
                        network_id, network_name, device_serial, device_name
                    ).set("1" if device_details["status"] == "online" else "0")

                if "usingCellularFailover" in device_details:
                    device_cellular_failover_metric.labels(
                        network_id, network_name, device_serial, device_name
                    ).set("1" if device_details["usingCellularFailover"] else "0")

            if "uplinks" in device_details:
                for uplink_name, uplink_details in device_details["uplinks"].items():
                    if "status" in uplink_details:
                        device_uplink_status_metric.labels(
                            network_id,
                            network_name,
                            device_serial,
                            device_name,
                            uplink_name,
                        ).set(uplink_status_mappings[uplink_details["status"]])
                    if "latency" in uplink_details:
                        device_uplink_latency_metric.labels(
                            network_id,
                            network_name,
                            device_serial,
                            device_name,
                            uplink_name,
                        ).set(uplink_details["latency"])
                    if "loss" in uplink_details:
                        device_uplink_loss_metric.labels(
                            network_id,
                            network_name,
                            device_serial,
                            device_name,
                            uplink_name,
                        ).set(uplink_details["loss"])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = configargparse.ArgumentParser(
        description="Per-User traffic stats Prometheus exporter for Meraki API."
    )
    parser.add_argument(
        "-k",
        metavar="API_KEY",
        type=str,
        required=True,
        env_var="MERAKI_API_KEY",
        help="API Key",
    )
    parser.add_argument(
        "-p",
        metavar="http_port",
        type=int,
        default=9822,
        help="HTTP port to listen for Prometheus scraper, default 9822",
    )
    parser.add_argument(
        "-i",
        metavar="bind_to_ip",
        type=str,
        default="",
        help="IP address where HTTP server will listen, default all interfaces",
    )
    parser.add_argument(
        "-m",
        metavar="API_URL",
        type=str,
        help="The URL to use for the Meraki API",
        default="https://api.meraki.com/api/v1",
    )
    parser.add_argument(
        "-o",
        metavar="ORG_ID",
        type=str,
        help="The Meraki API Organization ID",
        required=True,
    )
    args = vars(parser.parse_args())
    HTTP_PORT_NUMBER = args["p"]
    HTTP_BIND_IP = args["i"]
    API_KEY = args["k"]
    API_URL = args["m"]
    ORG_ID = args["o"]

    # Start up the server to expose the metrics.
    start_http_server(HTTP_PORT_NUMBER, addr=HTTP_BIND_IP)

    while True:
        update_metrics()
        time.sleep(30)
