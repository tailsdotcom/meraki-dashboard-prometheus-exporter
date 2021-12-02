# Meraki API Exporter for Prometheus
Prometheus exporter to collect some data from Meraki dashboard via API

### Exported metrics
Not all devices exports all metrics.

| metric | unit | description |
| --- | --- | --- |
| meraki_device_uplink_latency | seconds | Latency for a given uplink on a device
| meraki_device_uplink_loss | % | Packet loss for a given uplink on a device
| meraki_device_status | int | 0 - Offline <br> 1 - Online
| meraki_device_using_cellular_failover| int | 1 - using cellular <br> 0 - using main Uplink
| meraki_device_uplink_status | int | 'active': 0 <br> 'ready': 1 <br> 'connecting': 2 <br> 'not connected': 3 <br> 'failed': 4
| meraki_network_uplink_sent | bytes per minute | Bytes sent by the uplink in a minute
| meraki_network_uplink_received | bytes per minute | Bytes received by the uplink in a minute
| request_processing_seconds | sec | Total processing time for all hosts, exported once |

### Labels
All metrics but __request_processing_seconds__ has following Labels
| . | . | . |
| --- | --- | --- |
| networkId | string | Network ID
| networkName | string | Network name

* **meraki_network_uplink** metrics also carry `uplink` label containing uplink name.
* **meraki_device** metrics also carry `serial` and `deviceName` labels. Where name is not set, deviceName contains the MAC address.
* **meraki_device_uplink** metrics have all of the above labels.

### How to Use
```
pip install -r requirements.txt
```
You need to provide API Key from meraki portal as argument when starting exporter.<br>
**DO NOT USE KEYS WITH FULL ADMIN PRIVILEGES**<br>
Exporter is listening on port 9822 on all interfaces by default

```
  -h, --help     show this help message and exit
  -k API_KEY     API Key (Required, can also be specified using `MERAKI_API_KEY` environment variable)
  -o org_id      Meraki Organization ID number (Required, can also be specified using `ORG_ID` environment variable)
  -p http_port   HTTP port to listen for Prometheus scraper, default 9822
  -i bind_to_ip  IP address where HTTP server will listen, default all interfaces
```

**example prometheus.yml**
```
scrape_configs:
  - job_name: 'Meraki'
    scrape_interval: 120s
    scrape_timeout: 40s
    metrics_path: /
    file_sd_configs:
      - files:
        - /etc/prometheus/meraki-targets.yml
```
Please check **/systemd** folder for systemd services and timers configuration files, if your system uses it.

### Docker

There is a Docker image available at `ghcr.io/TheHolm/meraki-dashboard-prometheus-exporter`. You can run the exporter with a command like:

`docker run -p 9822:9822 -e ORG_ID=<org id> -e MERAKI_API_KEY=<api key> ghcr.io/TheHolm/meraki-dashboard-prometheus-exporter`
