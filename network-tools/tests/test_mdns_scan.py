"""Unit tests for network-tools/mdns_scan.py.

First pytest suite in the repository - runs locally with `cd network-tools && python3 -m pytest tests/`.
No CI hook. To run: `uvx --from pytest pytest tests/` (paho-mqtt does NOT need to be installed -
the tests stub paho.mqtt.client via sys.modules).
"""
import json
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "mdns_scan.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))

import mdns_scan  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def install_mock_paho(mock_client_cls):
    """Install a stub paho.mqtt.client module into sys.modules so mdns_scan can import it.

    Returns the mock_client instance to be inspected by the test.
    Uses real types.ModuleType for paho / paho.mqtt so the Python import system correctly resolves
    the nested submodule; only the leaf (paho.mqtt.client) gets the mock attributes.
    """
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_callback_api_version = MagicMock()
    mock_callback_api_version.VERSION1 = "VERSION1"

    paho = types.ModuleType("paho")
    paho_mqtt = types.ModuleType("paho.mqtt")
    paho_mqtt_client = types.ModuleType("paho.mqtt.client")
    paho_mqtt_client.Client = mock_client_cls
    paho_mqtt_client.CallbackAPIVersion = mock_callback_api_version
    paho.mqtt = paho_mqtt
    paho_mqtt.client = paho_mqtt_client

    sys.modules["paho"] = paho
    sys.modules["paho.mqtt"] = paho_mqtt
    sys.modules["paho.mqtt.client"] = paho_mqtt_client
    return mock_client


def uninstall_mock_paho():
    for key in ("paho.mqtt.client", "paho.mqtt", "paho"):
        sys.modules.pop(key, None)


# ----------------------------- parse_avahi_line -----------------------------


class TestParseAvahiLine:
    def test_parses_parsable_format(self):
        line = (
            "=;eth0;IPv4;Brother HL-L3270CDW series;_ipp._tcp;local;"
            "brother.local;192.168.178.50;631;\"txtvers=1\";\"rp=printers/Brother\""
        )
        p = mdns_scan.parse_avahi_line(line)
        assert p is not None
        assert p["event"] == "="
        assert p["iface"] == "eth0"
        assert p["proto"] == "IPv4"
        assert p["name"] == "Brother HL-L3270CDW series"
        assert p["type"] == "_ipp._tcp"
        assert p["host"] == "brother.local"
        assert p["address"] == "192.168.178.50"
        assert p["port"] == 631
        assert p["txt"] == ["txtvers=1", "rp=printers/Brother"]

    def test_handles_utf8_and_special_chars(self):
        line = "=;eth0;IPv4;Drucker Kueche & Co;_ipp._tcp;local;kueche.local;192.168.178.99;631;"
        p = mdns_scan.parse_avahi_line(line)
        assert p is not None
        assert "Kueche" in p["name"]
        assert "&" in p["name"]

    def test_handles_event_marker_plus(self):
        line = "+;eth0;IPv4;New Probe;_ipp._tcp;local;new.local;192.168.178.55;631;"
        p = mdns_scan.parse_avahi_line(line)
        assert p is not None
        assert p["event"] == "+"

    def test_returns_none_for_empty_line(self):
        assert mdns_scan.parse_avahi_line("") is None

    def test_returns_none_for_garbage(self):
        assert mdns_scan.parse_avahi_line("not a parsable line") is None

    def test_returns_none_for_too_few_fields(self):
        assert mdns_scan.parse_avahi_line(";only;three;fields") is None


# ----------------------------- matches_filter -----------------------------


class TestFilterMatch:
    parsed = {
        "name": "Brother HL-L3270CDW series",
        "host": "brother.local",
        "address": "192.168.178.50",
    }

    def test_empty_filter_matches_all(self):
        assert mdns_scan.matches_filter(self.parsed, []) is True

    def test_none_filter_matches_all(self):
        assert mdns_scan.matches_filter(self.parsed, None) is True

    def test_substring_case_insensitive(self):
        assert mdns_scan.matches_filter(self.parsed, ["brother"]) is True
        assert mdns_scan.matches_filter(self.parsed, ["BROTHER"]) is True

    def test_match_against_name(self):
        assert mdns_scan.matches_filter(self.parsed, ["HL-L3270CDW"]) is True

    def test_match_against_host(self):
        assert mdns_scan.matches_filter(self.parsed, ["brother.local"]) is True

    def test_match_against_address(self):
        assert mdns_scan.matches_filter(self.parsed, ["192.168.178.50"]) is True
        assert mdns_scan.matches_filter(self.parsed, ["192.168.178"]) is True

    def test_no_match_returns_false(self):
        assert mdns_scan.matches_filter(self.parsed, ["HP", "Canon"]) is False

    def test_multiple_patterns_any_match(self):
        assert mdns_scan.matches_filter(self.parsed, ["HP", "Brother"]) is True


# ----------------------------- classify -----------------------------


class TestClassify:
    sample_parsed = [
        {
            "event": "=", "iface": "eth0", "proto": "IPv4",
            "name": "Brother HL-L3270CDW series", "type": "_ipp._tcp",
            "domain": "local", "host": "brother.local",
            "address": "192.168.178.50", "port": 631, "txt": [],
        }
    ]

    def test_no_match_returns_not_found(self):
        result = mdns_scan.classify(self.sample_parsed, ["HP"], 5)
        assert result["state"] == "not_found"
        assert result["matched"] is None

    def test_match_resolved_returns_online(self):
        with patch("mdns_scan.resolve_host", return_value=True):
            result = mdns_scan.classify(self.sample_parsed, [], 5)
        assert result["state"] == "online"
        assert result["matched"]["host"] == "brother.local"

    def test_match_unresolved_returns_announced_unresolved(self):
        with patch("mdns_scan.resolve_host", return_value=False):
            result = mdns_scan.classify(self.sample_parsed, [], 5)
        assert result["state"] == "announced_unresolved"
        assert result["matched"] is not None

    def test_empty_results_returns_not_found(self):
        result = mdns_scan.classify([], [], 5)
        assert result["state"] == "not_found"


# ----------------------------- _run_avahi_browse timeout -----------------------------


class TestAvahiBrowseTimeout:
    def test_timeout_returns_empty_and_error(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5)):
            parsed, err = mdns_scan._run_avahi_browse("_ipp._tcp", 5)
        assert parsed == []
        assert "failed" in err.lower() or "timed out" in err.lower()

    def test_empty_output_returns_no_output_error(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            parsed, err = mdns_scan._run_avahi_browse("_ipp._tcp", 5)
        assert parsed == []
        assert err == "no output"

    def test_parsable_output_filters_going_away(self):
        mock_result = MagicMock()
        mock_result.stdout = (FIXTURES / "avahi_browse_online.txt").read_text()
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            parsed, err = mdns_scan._run_avahi_browse("_ipp._tcp", 5)
        events = [p["event"] for p in parsed]
        assert "-" not in events
        assert "=" in events or "+" in events
        assert err == ""

    def test_empty_fixture_returns_no_output_error(self):
        mock_result = MagicMock()
        mock_result.stdout = (FIXTURES / "avahi_browse_empty.txt").read_text()
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            parsed, err = mdns_scan._run_avahi_browse("_ipp._tcp", 5)
        assert parsed == []
        assert err == "no output"


# ----------------------------- publish_mqtt -----------------------------


class TestMqttPublish:
    def _monitor(self):
        return {
            "name": "test_monitor",
            "enabled": True,
            "service_types": ["_ipp._tcp"],
            "filter": [],
            "interval": 60,
            "timeout": 10,
            "topic_prefix": "homeassistant/monitor/test",
            "device_name": "Test Monitor",
        }

    def _result(self):
        return {
            "name": "test_monitor",
            "state": "online",
            "timestamp": "2026-08-22T12:00:00+00:00",
            "service_type": "_ipp._tcp",
            "service_name": "Test Printer",
            "hostname": "test.local",
            "address": "192.168.178.50",
            "port": 631,
            "txt_records": [],
            "error": None,
            "duration_ms": 100,
            "filter": [],
            "service_types_scanned": ["_ipp._tcp"],
        }

    def _options(self):
        return {
            "mqtt_enabled": True,
            "mqtt_host": "core-mosquitto",
            "mqtt_port": 1883,
            "mqtt_username": "",
            "mqtt_password": "",
            "mqtt_discovery_prefix": "homeassistant",
        }

    def _install_mock_paho(self):
        """Install a stub paho.mqtt.client module into sys.modules so mdns_scan can import it.

        Returns (mock_client_instance, mock_client_class) for assertions.
        """
        mock_client_cls = MagicMock()
        mock_client = install_mock_paho(mock_client_cls)
        return mock_client, mock_client_cls

    def _uninstall_mock_paho(self):
        uninstall_mock_paho()

    def test_publish_skipped_when_mqtt_disabled(self):
        opts = self._options()
        opts["mqtt_enabled"] = False
        mdns_scan.publish_mqtt(self._monitor(), self._result(), opts, "test_monitor")

    def test_publish_calls_retain_for_every_publish(self):
        mock_client, _ = self._install_mock_paho()
        try:
            mdns_scan.publish_mqtt(
                self._monitor(), self._result(), self._options(), "test_monitor"
            )
        finally:
            self._uninstall_mock_paho()
        retain_calls = [
            c for c in mock_client.publish.call_args_list if c.kwargs.get("retain") is True
        ]
        # 3 discovery configs + state + details + last_check + birth = 7
        assert len(retain_calls) >= 7

    def test_state_online_publishes_online(self):
        mock_client, _ = self._install_mock_paho()
        try:
            mdns_scan.publish_mqtt(
                self._monitor(), self._result(), self._options(), "test_monitor"
            )
        finally:
            self._uninstall_mock_paho()
        state_calls = [
            c for c in mock_client.publish.call_args_list
            if c.args and isinstance(c.args[0], str) and c.args[0].endswith("/state")
        ]
        assert any(c.args[1] == "online" for c in state_calls)

    def test_state_error_publishes_unknown(self):
        result = self._result()
        result["state"] = "error"
        mock_client, _ = self._install_mock_paho()
        try:
            mdns_scan.publish_mqtt(
                self._monitor(), result, self._options(), "test_monitor"
            )
        finally:
            self._uninstall_mock_paho()
        state_calls = [
            c for c in mock_client.publish.call_args_list
            if c.args and isinstance(c.args[0], str) and c.args[0].endswith("/state")
        ]
        assert any(c.args[1] == "unknown" for c in state_calls)

    def test_discovery_device_block_uses_slug(self):
        mock_client, _ = self._install_mock_paho()
        try:
            mdns_scan.publish_mqtt(
                self._monitor(), self._result(), self._options(), "my_slug"
            )
        finally:
            self._uninstall_mock_paho()
        all_payloads = [
            c.args[1] for c in mock_client.publish.call_args_list if len(c.args) >= 2
        ]
        assert any("networktools_mdns_my_slug" in str(p) for p in all_payloads)

    def test_publish_failure_does_not_raise(self):
        # Simulate paho Client.connect raising OSError
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.connect.side_effect = OSError("broker down")
        install_mock_paho(mock_client_cls)
        try:
            # Should swallow OSError and log, not raise
            mdns_scan.publish_mqtt(
                self._monitor(), self._result(), self._options(), "test_monitor"
            )
        finally:
            self._uninstall_mock_paho()

    def test_shared_availability_birth_published(self):
        mock_client, _ = self._install_mock_paho()
        try:
            mdns_scan.publish_mqtt(
                self._monitor(), self._result(), self._options(), "test_monitor"
            )
        finally:
            self._uninstall_mock_paho()
        avail_calls = [
            c for c in mock_client.publish.call_args_list
            if c.args and c.args[0] == "network-tools/arping/availability"
        ]
        assert len(avail_calls) >= 1
        assert avail_calls[0].args[1] == "online"
        assert avail_calls[0].kwargs.get("retain") is True


# ----------------------------- run_monitor -----------------------------


class TestRunMonitor:
    def test_run_monitor_returns_state_online(self):
        monitor = {
            "name": "test",
            "service_types": ["_ipp._tcp"],
            "filter": [],
            "timeout": 5,
        }
        with patch(
            "mdns_scan._run_avahi_browse",
            return_value=(
                [
                    {
                        "event": "=", "iface": "eth0", "proto": "IPv4",
                        "name": "X", "type": "_ipp._tcp", "domain": "local",
                        "host": "x.local", "address": "192.168.178.1",
                        "port": 631, "txt": [],
                    }
                ],
                "",
            ),
        ):
            with patch("mdns_scan.resolve_host", return_value=True):
                result = mdns_scan.run_monitor(monitor)
        assert result["state"] == "online"

    def test_run_monitor_handles_avahi_error_state_error(self):
        monitor = {
            "name": "test",
            "service_types": ["_ipp._tcp"],
            "filter": [],
            "timeout": 5,
        }
        with patch(
            "mdns_scan._run_avahi_browse",
            return_value=([], "avahi-browse failed: timeout"),
        ):
            result = mdns_scan.run_monitor(monitor)
        assert result["state"] == "error"
        assert "timeout" in result["error"]


class TestMainIndependence:
    """mDNS-Fehler duerfen den ARPing-Loop NICHT stoppen.

    We simulate the run.sh semantics: mdns_loop wraps python3 in `|| log`, so a non-zero exit does not
    break the loop. The contract here is: mdns_scan.main() either succeeds or exits non-zero - it does
    NOT raise.
    """

    def test_main_does_not_raise_on_monitor_crash(self, tmp_path):
        options_path = tmp_path / "options.json"
        options_path.write_text(
            json.dumps(
                {
                    "log_level": "error",
                    "mdns_monitors": [
                        {
                            "name": "broken",
                            "enabled": True,
                            "service_types": ["_ipp._tcp"],
                            "timeout": 5,
                        }
                    ],
                    "mqtt_enabled": False,
                }
            )
        )
        with patch.object(mdns_scan, "OPTIONS_FILE", options_path):
            with patch("mdns_scan.run_monitor", side_effect=Exception("simulated crash")):
                # main() should catch the exception and continue, not raise
                mdns_scan.main()

    def test_main_writes_empty_output_when_no_monitors(self, tmp_path):
        options_path = tmp_path / "options.json"
        output_path = tmp_path / "mdns_scan.json"
        options_path.write_text(json.dumps({"log_level": "error", "mdns_monitors": []}))
        with patch.object(mdns_scan, "OPTIONS_FILE", options_path):
            with patch.object(mdns_scan, "OUTPUT_FILE", output_path):
                mdns_scan.main()
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["results"] == []


class TestDiscoveryPayloads:
    """HA Discovery payload structure: each monitor emits 3 configs sharing a device block."""

    def _monitor(self, slug="brother"):
        return {
            "name": "Brother AirPrint",
            "service_types": ["_ipp._tcp"],
            "filter": [],
            "interval": 60,
            "timeout": 10,
            "topic_prefix": "homeassistant/monitor/brother",
            "device_name": "Brother HL-L3270CDW",
        }

    def test_three_discovery_payloads_with_correct_kinds(self):
        payloads = mdns_scan._build_discovery_payloads(
            self._monitor(), "homeassistant", "brother"
        )
        assert "binary_sensor" in payloads
        assert "sensor_state" in payloads
        assert "sensor_last_check" in payloads
        assert payloads["_topic_prefix"] == "homeassistant/monitor/brother"

    def test_binary_sensor_uses_connectivity_device_class(self):
        payloads = mdns_scan._build_discovery_payloads(
            self._monitor(), "homeassistant", "brother"
        )
        bs = payloads["binary_sensor"]
        assert bs["device_class"] == "connectivity"
        assert bs["payload_on"] == "ON"
        assert bs["payload_off"] == "OFF"

    def test_last_check_sensor_uses_timestamp_device_class(self):
        payloads = mdns_scan._build_discovery_payloads(
            self._monitor(), "homeassistant", "brother"
        )
        lc = payloads["sensor_last_check"]
        assert lc["device_class"] == "timestamp"

    def test_expire_after_doubles_interval(self):
        payloads = mdns_scan._build_discovery_payloads(
            self._monitor(), "homeassistant", "brother"
        )
        # interval is 60s in the test monitor
        assert payloads["binary_sensor"]["expire_after"] == 120
        assert payloads["sensor_state"]["expire_after"] == 120
        assert payloads["sensor_last_check"]["expire_after"] == 120

    def test_default_topic_prefix_when_unspecified(self):
        monitor = self._monitor()
        del monitor["topic_prefix"]
        payloads = mdns_scan._build_discovery_payloads(monitor, "homeassistant", "brother")
        assert payloads["_topic_prefix"] == "homeassistant/monitor/networktools_mdns_brother"

    def test_state_payload_mappings(self):
        assert mdns_scan._state_to_binary("online") == "ON"
        assert mdns_scan._state_to_binary("not_found") == "OFF"
        assert mdns_scan._state_to_binary("announced_unresolved") == "OFF"
        assert mdns_scan._state_to_binary("error") == "OFF"
        assert mdns_scan._state_text_for_sensor("online") == "online"
        assert mdns_scan._state_text_for_sensor("not_found") == "offline"
        assert mdns_scan._state_text_for_sensor("announced_unresolved") == "offline"
        assert mdns_scan._state_text_for_sensor("error") == "unknown"