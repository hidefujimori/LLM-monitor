#!/usr/bin/env python3
import logging
import logging.handlers
import os
import signal
import sys
import time

import yaml

from gpu_collector import GPUCollector
from ollama_collector import OllamaCollector
from splunk_hec import SplunkHEC

running = True


def handle_signal(signum, frame):
    global running
    logger.info("Received signal %d, shutting down...", signum)
    running = False


def setup_logging(level: str, log_file: str) -> None:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    log_level = getattr(logging, level.upper(), logging.INFO)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5),
    ]
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    config_path = os.environ.get("CONFIG_PATH", os.path.join(os.path.dirname(__file__), "../config/config.yaml"))
    config = load_config(config_path)

    setup_logging(
        config["logging"]["level"],
        os.path.join(os.path.dirname(__file__), "..", config["logging"]["file"]),
    )

    global logger
    logger = logging.getLogger(__name__)
    logger.info("LLM Monitor collector starting")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    hec = SplunkHEC(
        hec_url=config["splunk"]["hec_url"],
        hec_token=config["splunk"]["hec_token"],
        index=config["splunk"]["index"],
        source=config["splunk"]["source"],
        sourcetype=config["splunk"]["sourcetype"],
        verify_ssl=config["splunk"]["verify_ssl"],
    )

    ollama = OllamaCollector(
        base_url=config["ollama"]["base_url"],
        timeout=config["ollama"]["timeout"],
    )

    gpu = GPUCollector()
    interval = config["collection"]["interval_seconds"]
    gpu_enabled = config["collection"]["gpu_enabled"]

    logger.info("Collecting every %d seconds. GPU collection: %s", interval, gpu_enabled)

    while running:
        events = []

        try:
            ollama_data = ollama.collect()
            events.append(ollama_data)
            logger.info("Ollama: status=%s, models=%d, running=%d",
                        ollama_data["status"], ollama_data["model_count"],
                        ollama_data["running_model_count"])
        except Exception as e:
            logger.error("Ollama collection error: %s", e)

        if gpu_enabled:
            try:
                gpu_data = gpu.collect()
                events.append(gpu_data)
                logger.info("GPU: count=%d, vram_used=%.1f/%.1f MB",
                            gpu_data["gpu_count"], gpu_data["used_vram_mb"],
                            gpu_data["total_vram_mb"])
            except Exception as e:
                logger.error("GPU collection error: %s", e)

        if events:
            success = hec.send_batch(events)
            if not success:
                logger.warning("Failed to send %d events to Splunk HEC", len(events))

        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("LLM Monitor collector stopped")


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    main()
