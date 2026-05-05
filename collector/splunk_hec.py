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

    def send_batch(self, events: list[dict[str, Any]]) -> bool:
        """Send a batch of events. Returns True on success, False on any failure."""
        if not events:
            return True

        batch = ""
        ts = time.time()
        for event in events:
            payload = {**self.default_meta, "event": event, "time": ts}
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
            logger.debug("HEC send OK: %d events", len(events))
            return True
        except requests.exceptions.ConnectionError:
            logger.warning("Splunk HEC unreachable (%s)", self.hec_url)
            return False
        except requests.exceptions.Timeout:
            logger.warning("Splunk HEC timed out")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error("Splunk HEC HTTP error: %s", e)
            return False
        except requests.exceptions.RequestException as e:
            logger.error("Splunk HEC send failed: %s", e)
            return False
