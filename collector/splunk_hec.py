import json
import logging
import time
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class SplunkHEC:
    def __init__(self, hec_url: str, hec_token: str, index: str,
                 source: str, sourcetype: str, verify_ssl: bool = False):
        self.hec_url = hec_url
        self.headers = {
            "Authorization": f"Splunk {hec_token}",
            "Content-Type": "application/json",
        }
        self.default_meta = {
            "index": index,
            "source": source,
            "sourcetype": sourcetype,
        }
        self.verify_ssl = verify_ssl

    def send(self, event: dict[str, Any], metadata: dict[str, Any] | None = None) -> bool:
        payload = {**self.default_meta, **(metadata or {})}
        payload["event"] = event
        payload["time"] = time.time()

        try:
            response = requests.post(
                self.hec_url,
                headers=self.headers,
                data=json.dumps(payload),
                verify=self.verify_ssl,
                timeout=10,
            )
            response.raise_for_status()
            logger.debug("HEC send OK: %s", response.json())
            return True
        except requests.exceptions.RequestException as e:
            logger.error("HEC send failed: %s", e)
            return False

    def send_batch(self, events: list[dict[str, Any]]) -> bool:
        batch = ""
        for event in events:
            payload = {**self.default_meta, "event": event, "time": time.time()}
            batch += json.dumps(payload) + "\n"

        try:
            response = requests.post(
                self.hec_url,
                headers=self.headers,
                data=batch,
                verify=self.verify_ssl,
                timeout=10,
            )
            response.raise_for_status()
            logger.debug("HEC batch send OK: %d events", len(events))
            return True
        except requests.exceptions.RequestException as e:
            logger.error("HEC batch send failed: %s", e)
            return False
