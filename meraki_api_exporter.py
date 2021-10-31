import threading
import time

import configargparse
import meraki
from prometheus_client import Gauge, start_http_server


def get_devices(devices, dashboard, organizationId):
    devices.extend(
        dashboard.organizations.getOrganizationDevicesStatuses(organizationId=organizationId, total_pages="all"))
    print('Got', len(devices), 'Devices')


def get_device_statuses(devicesdtatuses, dashboard, organizationId):
    devicesdtatuses.extend(
        dashboard.organizations.getOrganizationDevicesUplinksLossAndLatency(organizationId=organizationId, ip='8.8.8.8',
                                                                            timespan="120", total_pages="all"))
    print('Got ', len(devicesdtatuses), 'Device Statuses')


def get_uplink_statuses(uplinkstatuses, dashboard, organizationId):
    uplinkstatuses.extend(
        dashboard.appliance.getOrganizationApplianceUplinkStatuses(organizationId=organizationId, total_pages="all"))
    print('Got ', len(uplinkstatuses), 'Uplink Statuses')


def get_organizarion(org_data, dashboard, organizationId):
    org_data.update(dashboard.organizations.getOrganization(organizationId=organizationId))


def get_usage(dashboard, organizationId):
    # launching threads to collect data.
    # if more indexes is requred it is good time to conver it to loop.

    devices = []
    t1 = threading.Thread(target=get_devices, args=(devices, dashboard, organizationId))
    t1.start()

    devicesdtatuses = []
    t2 = threading.Thread(target=get_device_statuses, args=(devicesdtatuses, dashboard, organizationId))
    t2.start()

    uplinkstatuses = []
    t3 = threading.Thread(target=get_uplink_statuses, args=(uplinkstatuses, dashboard, organizationId))
    t3.start()

    org_data = {}
    t4 = threading.Thread(target=get_organizarion, args=(org_data, dashboard, organizationId))
    t4.start()

    t1.join()
    t2.join()
    t3.join()
    t4.join()

    print('Combining collected data\n')

    the_list = {}
    values_list = ['name', 'model', 'mac', 'wan1Ip', 'wan2Ip', 'lanIp', 'publicIp', 'networkId', 'status',
                   'usingCellularFailover']
    for device in devices:
        the_list[device['serial']] = {}
        the_list[device['serial']]['orgName'] = org_data['name']
        for value in values_list:
            try:
                if device[value] is not None:
                    the_list[device['serial']][value] = device[value]
            except KeyError:
                pass

    for device in devicesdtatuses:
        try:
            the_list[device['serial']]  # should give me KeyError if devices was not picket up by previous search.
        except KeyError:
            the_list[device['serial']] = {"missing data": True}

        the_list[device['serial']]['latencyMs'] = device['timeSeries'][-1]['latencyMs']
        the_list[device['serial']]['lossPercent'] = device['timeSeries'][-1]['lossPercent']

    for device in uplinkstatuses:
        try:
            the_list[device['serial']]  # should give me KeyError if devices was not picket up by previous search.
        except KeyError:
            the_list[device['serial']] = {"missing data": True}
        the_list[device['serial']]['uplinks'] = {}
        for uplink in device['uplinks']:
            the_list[device['serial']]['uplinks'][uplink['interface']] = uplink['status']

    print('Done')
    return (the_list)


# end of get_usage()


REQUEST_TIME = Gauge('request_processing_seconds', 'Time spent processing request')
label_list = ['serial', 'name', 'networkId', 'orgName', 'orgId']
latency_metric = Gauge('meraki_device_latency', 'Latency', label_list)
loss_metric = Gauge('meraki_device_loss_percent', 'Loss Percent', label_list)
device_status_metric = Gauge('meraki_device_status', 'Device Status', label_list)
cellular_failover_metric = Gauge('meraki_device_using_cellular_failover', 'Cellular Failover', label_list)
device_uplink_status_metric = Gauge('meraki_device_uplink_status', 'Device Uplink Status', label_list + ['uplink'])


@REQUEST_TIME.time()
def update_metrics():
    dashboard = meraki.DashboardAPI(API_KEY, base_url=API_URL, output_log=False, print_console=True)
    organizationId = ORG_ID

    host_stats = get_usage(dashboard, organizationId)
    print("Reporting on:", len(host_stats), "hosts")
    '''{ 'latencyMs': 23.7,
         'lossPercent': 0.0,
         'name': 'TestSite',
         'mac': 'e0:cb:00:00:00:00'
         'networkId': 'L_12345678',
         'publicIp': '1.2.3.4',
         'status': 'online',
         'uplinks': {'cellular': 'ready', 'wan1': 'active'},
         'usingCellularFailover': False,
         'wan1Ip': '1.2.3.4'}
    '''
    # uplink statuses
    uplink_statuses = {'active': 0,
                       'ready': 1,
                       'connecting': 2,
                       'not connected': 3,
                       'failed': 4}

    for host in host_stats.keys():
        try:
            name_label = host_stats[host]['name'] if host_stats[host]['name'] != "" else host_stats[host]['mac']
            latency_metric.labels(host, name_label, host_stats[host]['networkId'], host_stats[host]['orgName'],
                                  organizationId)
        except KeyError:
            break
        # values={ 'latencyMs': lambda a : str(a)}
        try:
            if host_stats[host]['latencyMs'] is not None:
                latency_metric.labels(host, name_label, host_stats[host]['networkId'], host_stats[host]['orgName'],
                                      organizationId).set(host_stats[host]['latencyMs'] / 1000)

            if host_stats[host]['lossPercent'] is not None:
                loss_metric.labels(host, name_label, host_stats[host]['networkId'], host_stats[host]['orgName'],
                                   organizationId).set(host_stats[host]['lossPercent'])
        except KeyError:
            pass
        try:
            device_status_metric.labels(host, name_label, host_stats[host]['networkId'], host_stats[host]['orgName'],
                                        organizationId).set('1' if host_stats[host]['status'] == 'online' else '0')
        except KeyError:
            pass
        try:
            cellular_failover_metric.labels(host, name_label, host_stats[host]['networkId'],
                                            host_stats[host]['orgName'],
                                            organizationId).set(
                '1' if host_stats[host]['usingCellularFailover'] else '0')
        except KeyError:
            pass
        if 'uplinks' in host_stats[host]:
            for uplink in host_stats[host]['uplinks'].keys():
                device_uplink_status_metric.labels(host, name_label, host_stats[host]['networkId'],
                                                   host_stats[host]['orgName'],
                                                   organizationId, uplink).set(
                    uplink_statuses[host_stats[host]['uplinks'][uplink]])


if __name__ == '__main__':
    parser = configargparse.ArgumentParser(description='Per-User traffic stats Prometheus exporter for Meraki API.')
    parser.add_argument('-k', metavar='API_KEY', type=str, required=True,
                        env_var='MERAKI_API_KEY', help='API Key')
    parser.add_argument('-p', metavar='http_port', type=int, default=9822,
                        help='HTTP port to listen for Prometheus scraper, default 9822')
    parser.add_argument('-i', metavar='bind_to_ip', type=str, default="",
                        help='IP address where HTTP server will listen, default all interfaces')
    parser.add_argument('-m', metavar='API_URL', type=str, help='The URL to use for the Meraki API',
                        default="https://api.meraki.com/api/v1")
    parser.add_argument('-o', metavar='ORG_ID', type=str, help='The Meraki API Organization ID',
                        default="1234")
    args = vars(parser.parse_args())
    HTTP_PORT_NUMBER = args['p']
    HTTP_BIND_IP = args['i']
    API_KEY = args['k']
    API_URL = args['m']
    ORG_ID = args['o']

    # Start up the server to expose the metrics.
    start_http_server(HTTP_PORT_NUMBER, addr=HTTP_BIND_IP)

    while True:
        update_metrics()
        time.sleep(30)
