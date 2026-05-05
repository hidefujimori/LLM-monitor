import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class OllamaCollector:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict | None:
        try:
            resp = requests.get(f"{self.base_url}{path}", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            logger.warning("Ollama not reachable at %s", self.base_url)
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Ollama request failed: %s", e)
            return None

    def collect(self) -> dict[str, Any]:
        models_data = self._get("/api/tags")
        running_data = self._get("/api/ps")
        version_data = self._get("/api/version")

        models = []
        if models_data and "models" in models_data:
            for m in models_data["models"]:
                models.append({
                    "name": m.get("name"),
                    "size_bytes": m.get("size"),
                    "size_gb": round(m.get("size", 0) / 1024**3, 2),
                    "modified_at": m.get("modified_at"),
                    "quantization": m.get("details", {}).get("quantization_level"),
                    "parameter_size": m.get("details", {}).get("parameter_size"),
                    "family": m.get("details", {}).get("family"),
                })

        running_models = []
        if running_data and "models" in running_data:
            for m in running_data["models"]:
                size_total = m.get("size", 0)
                size_vram = m.get("size_vram", 0)
                size_ram = max(size_total - size_vram, 0)
                offloaded = size_ram > 0

                running_models.append({
                    "name": m.get("name"),
                    # VRAM portion
                    "size_vram_bytes": size_vram,
                    "size_vram_gb": round(size_vram / 1024**3, 2),
                    # RAM offload portion
                    "size_ram_bytes": size_ram,
                    "size_ram_gb": round(size_ram / 1024**3, 2),
                    # Total (VRAM + RAM)
                    "size_total_bytes": size_total,
                    "size_total_gb": round(size_total / 1024**3, 2),
                    # Offload flag
                    "offloaded_to_ram": offloaded,
                    "expires_at": m.get("expires_at"),
                })

        total_vram_used_gb = round(
            sum(m["size_vram_gb"] for m in running_models), 2
        )
        total_ram_used_gb = round(
            sum(m["size_ram_gb"] for m in running_models), 2
        )

        return {
            "metric_type": "ollama",
            "status": "running" if models_data is not None else "unreachable",
            "version": version_data.get("version") if version_data else None,
            "model_count": len(models),
            "models": models,
            "running_model_count": len(running_models),
            "running_models": running_models,
            "running_total_vram_gb": total_vram_used_gb,
            "running_total_ram_gb": total_ram_used_gb,
            "any_offloaded_to_ram": any(m["offloaded_to_ram"] for m in running_models),
        }
