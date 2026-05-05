import logging
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class GPUCollector:
    def __init__(self):
        self._nvidia_smi = shutil.which("nvidia-smi")
        self._rocm_smi = shutil.which("rocm-smi")

    def _collect_nvidia(self) -> list[dict[str, Any]]:
        query = (
            "index,name,uuid,temperature.gpu,utilization.gpu,"
            "utilization.memory,memory.total,memory.used,memory.free,"
            "power.draw,power.limit,clocks.current.graphics,clocks.current.memory,"
            "fan.speed,pstate"
        )
        try:
            result = subprocess.run(
                [self._nvidia_smi, f"--query-gpu={query}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error("nvidia-smi error: %s", result.stderr)
                return []

            gpus = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 15:
                    continue

                def safe_float(v: str) -> float | None:
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        return None

                gpus.append({
                    "vendor": "nvidia",
                    "index": int(parts[0]),
                    "name": parts[1],
                    "uuid": parts[2],
                    "temperature_c": safe_float(parts[3]),
                    "gpu_utilization_pct": safe_float(parts[4]),
                    "memory_utilization_pct": safe_float(parts[5]),
                    "memory_total_mb": safe_float(parts[6]),
                    "memory_used_mb": safe_float(parts[7]),
                    "memory_free_mb": safe_float(parts[8]),
                    "memory_used_pct": round(
                        safe_float(parts[7]) / safe_float(parts[6]) * 100, 1
                    ) if safe_float(parts[6]) else None,
                    "power_draw_w": safe_float(parts[9]),
                    "power_limit_w": safe_float(parts[10]),
                    "clock_graphics_mhz": safe_float(parts[11]),
                    "clock_memory_mhz": safe_float(parts[12]),
                    "fan_speed_pct": safe_float(parts[13]),
                    "performance_state": parts[14],
                })
            return gpus
        except subprocess.TimeoutExpired:
            logger.error("nvidia-smi timed out")
            return []
        except Exception as e:
            logger.error("nvidia-smi collection error: %s", e)
            return []

    def _collect_rocm(self) -> list[dict[str, Any]]:
        try:
            result = subprocess.run(
                [self._rocm_smi, "--showtemp", "--showuse", "--showmeminfo", "vram",
                 "--showpower", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error("rocm-smi error: %s", result.stderr)
                return []

            import json
            data = json.loads(result.stdout)
            gpus = []
            for card_key, card_data in data.items():
                if not card_key.startswith("card"):
                    continue
                index = int(card_key.replace("card", ""))
                vram_total = float(card_data.get("VRAM Total Memory (B)", 0)) / 1024**2
                vram_used = float(card_data.get("VRAM Total Used Memory (B)", 0)) / 1024**2
                gpus.append({
                    "vendor": "amd",
                    "index": index,
                    "temperature_c": float(card_data.get("Temperature (Sensor edge) (C)", 0)),
                    "gpu_utilization_pct": float(card_data.get("GPU use (%)", 0)),
                    "memory_total_mb": vram_total,
                    "memory_used_mb": vram_used,
                    "memory_free_mb": vram_total - vram_used,
                    "memory_used_pct": round(vram_used / vram_total * 100, 1) if vram_total else None,
                    "power_draw_w": float(card_data.get("Average Graphics Package Power (W)", 0)),
                })
            return gpus
        except Exception as e:
            logger.error("rocm-smi collection error: %s", e)
            return []

    def collect(self) -> dict[str, Any]:
        gpus = []

        if self._nvidia_smi:
            gpus.extend(self._collect_nvidia())
        elif self._rocm_smi:
            gpus.extend(self._collect_rocm())
        else:
            logger.info("No GPU management tool found (nvidia-smi / rocm-smi)")

        total_vram_mb = sum(g.get("memory_total_mb") or 0 for g in gpus)
        used_vram_mb = sum(g.get("memory_used_mb") or 0 for g in gpus)

        return {
            "metric_type": "gpu",
            "gpu_count": len(gpus),
            "total_vram_mb": round(total_vram_mb, 1),
            "used_vram_mb": round(used_vram_mb, 1),
            "free_vram_mb": round(total_vram_mb - used_vram_mb, 1),
            "gpus": gpus,
        }
