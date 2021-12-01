import logging
import threading
import time

import configargparse
import meraki
from prometheus_client import Gauge, start_http_server


def get_devices(devices, dashboard, organizationId):
    try:
        devices.extend(
            dashboard.organizations.getOrganizationDevicesStatuses(
                organizationId=organizationId, total_pages="all"
            )
        )
        logging.info(f"Got {len(devices)} Devices")
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_device_statuses(devicestatuses, dashboard, organizationId):
    try:
        devicestatuses.extend(
            dashboard.organizations.getOrganizationDevicesUplinksLossAndLatency(
                organizationId=organizationId,
                ip="8.8.8.8",
                timespan="120",
                total_pages="all",
            )
        )
        logging.info(f"Got {len(devicestatuses)} Device Statuses")
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_uplink_statuses(uplinkstatuses, dashboard, organizationId):
    try:
        uplinkstatuses.extend(
            dashboard.appliance.getOrganizationApplianceUplinkStatuses(
                organizationId=organizationId, total_pages="all"
            )
        )
        logging.info(f"Got {len(uplinkstatuses)} Uplink Statuses")
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_uplink_usage(network_id, dashboard):
    try:
        uplink_usage_list = dashboard.appliance.getNetworkApplianceUplinksUsageHistory(networkId=network_id)
        uplink_usage_dict = {}
        for interface in uplink_usage_list[-1]["byInterface"]:
            uplink_usage_dict[interface["interface"]] = {
                "sent": interface["sent"],
                "received": interface["received"]
            }
        logging.info(f"Got {len(uplink_usage_dict.keys())} Uplink Usages for network {network_id}")
        return uplink_usage_dict
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_organization(org_data, dashboard, organizationId):
    try:
        org_data.update(
            dashboard.organizations.getOrganization(organizationId=organizationId)
        )
    except meraki.APIError as api_error:
        logging.warning(api_error)


def get_usage(dashboard, organizationId):
    # launching threads to collect data.
    # if more indexes is required it is good time to convert it to loop.

    devices = []
    t1 = threading.Thread(target=get_devices, args=(devices, dashboard, organizationId))
    t1.start()

    device_statuses = []
    t2 = threading.Thread(
        target=get_device_statuses, args=(device_statuses, dashboard, organizationId)
    )
    t2.start()

    uplink_statuses = []
    t3 = threading.Thread(
        target=get_uplink_statuses, args=(uplink_statuses, dashboard, organizationId)
    )
    t3.start()

    org_data = {}
    t4 = threading.Thread(
        target=get_organization, args=(org_data, dashboard, organizationId)
    )
    t4.start()

    t1.join()
    t2.join()
    t3.join()
    t4.join()

    uplink_usage_dict = {}
    for device in devices:
        network_id = device["networkId"]
        if network_id not in uplink_usage_dict:
            uplink_usage_dict[network_id] = get_uplink_usage(network_id, dashboard)

    logging.info("Combining collected data")

    the_dict = {}
    values_list = [
        "name",
        "model",
        "mac",
        "wan1Ip",
        "wan2Ip",
        "lanIp",
        "publicIp",
        "networkId",
        "status",
        "usingCellularFailover",
    ]
    for device in devices:
        device_serial = device["serial"]
        the_dict[device_serial] = {}
        the_dict[device_serial]["orgName"] = org_data["name"]
        for value in values_list:
            if value in device:
                the_dict[device_serial][value] = device[value]

    for device in device_statuses:
        device_serial = device["serial"]
        device_uplink = device["uplink"]
        if device_serial not in the_dict:
            the_dict[device_serial] = {"missing data": True}

        if "uplinks" not in the_dict[device_serial]:
            the_dict[device_serial]["uplinks"] = {}

        the_dict[device_serial]["uplinks"][device_uplink] = {
            "latencyMs": device["timeSeries"][-1]["latencyMs"],
            "lossPercent": device["timeSeries"][-1]["lossPercent"],
        }

    for device in uplink_statuses:
        device_serial = device["serial"]

        if device_serial not in the_dict:
            the_dict[device_serial] = {"missing data": True}

        if "uplinks" not in the_dict[device_serial]:
            the_dict[device_serial]["uplinks"] = {}

        for uplink in device["uplinks"]:
            device_uplink = uplink["interface"]
            if device_uplink not in the_dict[device_serial]["uplinks"]:
                the_dict[device_serial]["uplinks"][device_uplink] = {}

            the_dict[device_serial]["uplinks"][device_uplink]["status"] = uplink[
                "status"
            ]

            if device["networkId"] in uplink_usage_dict:
                if device_uplink in uplink_usage_dict[device["networkId"]]:
                    the_dict[device_serial]["uplinks"][device_uplink]["sent"] = uplink_usage_dict[device["networkId"]][device_uplink]["sent"]
                    the_dict[device_serial]["uplinks"][device_uplink]["received"] = uplink_usage_dict[device["networkId"]][device_uplink]["received"]

    logging.info("Done")
    return the_dict


# end of get_usage()


REQUEST_TIME = Gauge("request_processing_seconds", "Time spent processing request")
label_list = ["serial", "name", "networkId", "orgName", "orgId"]
latency_metric = Gauge("meraki_device_latency", "Latency", label_list + ["uplink"])
loss_metric = Gauge(
    "meraki_device_loss_percent", "Loss Percent", label_list + ["uplink"]
)
device_status_metric = Gauge("meraki_device_status", "Device Status", label_list)
cellular_failover_metric = Gauge(
    "meraki_device_using_cellular_failover", "Cellular Failover", label_list
)
device_uplink_status_metric = Gauge(
    "meraki_device_uplink_status", "Device Uplink Status", label_list + ["uplink"]
)
device_uplink_sent_metric = Gauge(
    "meraki_device_uplink_sent", "Device Uplink Sent", label_list + ["uplink"]
)
device_uplink_received_metric = Gauge(
    "meraki_device_uplink_received", "Device Uplink Received", label_list + ["uplink"]
)

@REQUEST_TIME.time()
def update_metrics():
    dashboard = meraki.DashboardAPI(API_KEY, base_url=API_URL, suppress_logging=True)
    organizationId = ORG_ID

    host_stats = get_usage(dashboard, organizationId)
    logging.info(f"Reporting on: {len(host_stats)} hosts")
    """{ 'latencyMs': 23.7,
         'lossPercent': 0.0,
         'name': 'TestSite',
         'mac': 'e0:cb:00:00:00:00'
         'networkId': 'L_12345678',
         'publicIp': '1.2.3.4',
         'status': 'online',
         'uplinks': {'cellular': 'ready', 'wan1': 'active'},
         'usingCellularFailover': False,
         'wan1Ip': '1.2.3.4'}
    """
    # uplink statuses
    uplink_status_mappings = {
        "active": 0,
        "ready": 1,
        "connecting": 2,
        "not connected": 3,
        "failed": 4,
    }

    for host in host_stats.keys():
        try:
            name_label = (
                host_stats[host]["name"]
                if host_stats[host]["name"] != ""
                else host_stats[host]["mac"]
            )
        except KeyError:
            break

        try:
            device_status_metric.labels(
                host,
                name_label,
                host_stats[host]["networkId"],
                host_stats[host]["orgName"],
                organizationId,
            ).set("1" if host_stats[host]["status"] == "online" else "0")
        except KeyError:
            pass

        try:
            cellular_failover_metric.labels(
                host,
                name_label,
                host_stats[host]["networkId"],
                host_stats[host]["orgName"],
                organizationId,
            ).set("1" if host_stats[host]["usingCellularFailover"] else "0")
        except KeyError:
            pass

        if "uplinks" in host_stats[host]:
            uplinks_dict = host_stats[host]["uplinks"]
            for uplink in uplinks_dict.keys():
                uplink_label_list = [
                    host,
                    name_label,
                    host_stats[host]["networkId"],
                    host_stats[host]["orgName"],
                    organizationId,
                    uplink,
                ]
                if "status" in uplinks_dict[uplink]:
                    device_uplink_status_metric.labels(*uplink_label_list).set(uplink_status_mappings[uplinks_dict[uplink]["status"]])

                if "latencyMs" in uplinks_dict[uplink]:
                    latency_metric.labels(*uplink_label_list).set(uplinks_dict[uplink]["latencyMs"] / 1000)

                if "lossPercent" in uplinks_dict[uplink]:
                    loss_metric.labels(*uplink_label_list).set(uplinks_dict[uplink]["lossPercent"])

                if "sent" in uplinks_dict[uplink]:
                    device_uplink_sent_metric.labels(*uplink_label_list).set(uplinks_dict[uplink]["sent"])

                if "received" in uplinks_dict[uplink]:
                    device_uplink_received_metric.labels(*uplink_label_list).set(uplinks_dict[uplink]["received"])

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
        default="1234",
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
