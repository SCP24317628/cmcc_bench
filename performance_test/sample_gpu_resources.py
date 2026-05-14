#!/usr/bin/env python3

import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Sample GPU resource usage through SSH.")
    parser.add_argument("--ssh-target", action="append", default=[], help="Format: role=user@host")
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--sample-count", type=int, default=3)
    parser.add_argument("--remote-command", default="mthreads-gmi -q -d MEMORY,UTILIZATION --json")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def extract_numbers(obj, wanted_keys):
    values = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in wanted_keys and isinstance(value, (int, float)):
                values.append(float(value))
            else:
                values.extend(extract_numbers(value, wanted_keys))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(extract_numbers(item, wanted_keys))
    return values


def sample_target(target, remote_command, interval_seconds, sample_count):
    role, ssh_host = target.split("=", 1)
    samples = []
    errors = []
    for _ in range(sample_count):
        try:
            result = subprocess.run(
                ["ssh", ssh_host, remote_command],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            gpu_utils = extract_numbers(payload, {"gpu", "gpu_util", "gpu_utilization", "utilization.gpu"})
            mem_utils = extract_numbers(payload, {"memory", "mem", "memory_util", "memory_utilization", "utilization.memory"})
            samples.append(
                {
                    "raw": payload,
                    "gpu_utils": gpu_utils,
                    "memory_utils": mem_utils,
                }
            )
        except Exception as exc:  # pragma: no cover - best effort collector
            errors.append(str(exc))
        time.sleep(interval_seconds)

    flat_gpu = [value for sample in samples for value in sample["gpu_utils"]]
    flat_mem = [value for sample in samples for value in sample["memory_utils"]]
    return {
        "role": role,
        "ssh_host": ssh_host,
        "sample_count": len(samples),
        "gpu_util_avg": round(statistics.mean(flat_gpu), 4) if flat_gpu else None,
        "gpu_util_max": round(max(flat_gpu), 4) if flat_gpu else None,
        "memory_util_avg": round(statistics.mean(flat_mem), 4) if flat_mem else None,
        "memory_util_max": round(max(flat_mem), 4) if flat_mem else None,
        "errors": errors,
        "samples": samples,
    }


def main():
    args = parse_args()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    results = {
        "targets": [],
        "interval_seconds": args.interval_seconds,
        "sample_count": args.sample_count,
    }
    for target in args.ssh_target:
        results["targets"].append(
            sample_target(target, args.remote_command, args.interval_seconds, args.sample_count)
        )
    Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
