from flask import Flask

app = Flask(__name__)


@app.route("/")
def root():
    return "Herp derp I'm an API"


@app.route("/api/v1/organizations")
def get_organizations():
    return """[
    {
        "id": "1234",
        "name": "My organization",
        "url": "https://dashboard.meraki.com/o/VjjsAd/manage/organization/overview",
        "api": { "enabled": true }
    }
]"""


@app.route("/api/v1/organizations/1234")
def get_organization():
    return """{
    "id": "1234",
    "name": "My organization",
    "url": "https://dashboard.meraki.com/o/VjjsAd/manage/organization/overview",
    "api": { "enabled": true }
}"""


@app.route("/api/v1/organizations/1234/apiRequests/overview")
def get_organization_api_requests_overview():
    return """{
    "responseCodeCounts": {
        "200": 50000,
        "201": 4000,
        "204": 1000,
        "400": 3500,
        "404": 1500,
        "429": 10000
    }
}"""


@app.route("/api/v1/organizations/1234/devices/statuses")
def get_organization_devices_statuses():
    return """[
    {
        "name": "My AP",
        "serial": "Q234-ABCD-5678",
        "mac": "00:11:22:33:44:55",
        "publicIp": "123.123.123.1",
        "networkId": "N_24329156",
        "status": "online",
        "lastReportedAt": "2018-02-11T00:00:00.090210Z",
        "lanIp": "1.2.3.4",
        "gateway": "1.2.3.5",
        "ipType": "dhcp",
        "primaryDns": "8.8.8.8",
        "secondaryDns": "8.8.4.4",
        "productType": null,
        "components": { "powerSupplies": [] }
    }
]"""


@app.route("/api/v1/organizations/1234/devices/uplinksLossAndLatency")
def get_organization_devices_uplinks_loss_and_latency():
    return """[
    {
        "networkId": "N_24329156",
        "serial": "Q234-ABCD-5678",
        "uplink": "wan1",
        "ip": "8.8.8.8",
        "timeSeries": [
            {
                "ts": "2019-01-31T18:46:13Z",
                "lossPercent": 5.3,
                "latencyMs": 194.9
            }
        ]
    }
]"""


@app.route("/api/v1/organizations/1234/appliance/uplink/statuses")
def get_organization_devices_uplink_statuses():
    return """[
    {
        "networkId": "N_24329156",
        "serial": "Q234-ABCD-5678",
        "model": "MX68C",
        "lastReportedAt": "2018-02-11T00:00:00Z",
        "uplinks": [
            {
                "interface": "wan1",
                "status": "active",
                "ip": "1.2.3.4",
                "gateway": "1.2.3.5",
                "publicIp": "123.123.123.1",
                "primaryDns": "8.8.8.8",
                "secondaryDns": "8.8.4.4",
                "ipAssignedBy": "static"
            },
            {
                "interface": "cellular",
                "status": "ready",
                "ip": "1.2.3.4",
                "provider": "at&t",
                "publicIp": "123.123.123.1",
                "model": "integrated",
                "signalStat": {
                    "rsrp": "-120",
                    "rsrq": "-13"
                },
                "connectionType": "4g",
                "apn": "internet",
                "iccid": "123456789"
            }
        ]
    }
]"""


if __name__ == '__main__':
    app.run(host="127.0.0.1", port=9823, debug=True)
