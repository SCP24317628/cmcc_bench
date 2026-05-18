#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_REMOTE_COMMAND = "mthreads-gmi -q -d MEMORY,UTILIZATION,POWER --json"
DEFAULT_CPU_COMMAND = r"LC_ALL=C top -bn1 | grep -E '^%Cpu|^Cpu\(s\)' | head -n 1"
LOCAL_TARGET_ALIASES = {"local", "self", "localhost", "127.0.0.1"}


def parse_args():
    parser = argparse.ArgumentParser(description="Sample GPU resource usage through SSH.")
    parser.add_argument(
        "--ssh-target",
        action="append",
        default=[],
        help="Format: name=user@host or name:group=user@host. Use local/self/localhost for local machine.",
    )
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument(
        "--sample-count",
        type=int,
        default=3,
        help="Fixed sample rounds in standalone mode. Ignored when using --run-command or --until-pid.",
    )
    parser.add_argument("--remote-command", default=DEFAULT_REMOTE_COMMAND)
    parser.add_argument(
        "--cpu-command",
        default=DEFAULT_CPU_COMMAND,
        help="Remote command used to sample host CPU utilization. Empty string disables CPU sampling.",
    )
    parser.add_argument("--output", required=True, help="Summary JSON output path.")
    parser.add_argument(
        "--detail-dir",
        default="",
        help="Directory for rotated detail shard files. Defaults to <output_stem>_details beside --output.",
    )
    parser.add_argument(
        "--detail-level",
        choices=["none", "parsed", "raw"],
        default="parsed",
        help="Store no detail lines, parsed sample lines, or parsed lines with full raw payload.",
    )
    parser.add_argument(
        "--chunk-max-gb",
        type=float,
        default=0.25,
        help="Max size per detail shard file in GB before rotation.",
    )
    parser.add_argument(
        "--run-command",
        default="",
        help="Run this command and sample from command start until command exit.",
    )
    parser.add_argument(
        "--until-pid",
        type=int,
        default=0,
        help="Sample until the given PID exits.",
    )
    parser.add_argument(
        "--post-stop-grace-seconds",
        type=float,
        default=0.0,
        help="Optional extra sampling window after wrapped command/PID exits.",
    )
    return parser.parse_args()


def parse_numeric_value(value):
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def normalize_metric_key(key):
    text = str(key).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def extract_numbers(obj, wanted_keys):
    values = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            normalized_key = normalize_metric_key(key)
            if normalized_key in wanted_keys:
                parsed = parse_numeric_value(value)
                if parsed is not None:
                    values.append(parsed)
            values.extend(extract_numbers(value, wanted_keys))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(extract_numbers(item, wanted_keys))
    return values


def parse_cpu_util_value(text):
    if not text:
        return None
    idle_match = re.search(r"(\d+(?:\.\d+)?)\s*id\b", text)
    if idle_match:
        try:
            idle = float(idle_match.group(1))
            return round(max(0.0, min(100.0, 100.0 - idle)), 4)
        except ValueError:
            return None
    usage_match = re.search(r"(\d+(?:\.\d+)?)\s*us\b", text)
    if usage_match:
        try:
            return round(float(usage_match.group(1)), 4)
        except ValueError:
            return None
    return None


class DetailShardWriter:
    def __init__(self, detail_dir: Path, max_bytes: int, enabled: bool):
        self.detail_dir = detail_dir
        self.max_bytes = max_bytes
        self.enabled = enabled
        self.file_index = 0
        self.current_file = None
        self.current_path = None
        self.current_bytes = 0
        self.files = []
        if self.enabled:
            self.detail_dir.mkdir(parents=True, exist_ok=True)

    def _rotate(self):
        if not self.enabled:
            return
        if self.current_file:
            self.current_file.close()
        self.file_index += 1
        self.current_path = self.detail_dir / f"samples_{self.file_index:05d}.jsonl"
        self.current_file = self.current_path.open("a", encoding="utf-8")
        self.current_bytes = self.current_path.stat().st_size if self.current_path.exists() else 0
        self.files.append(str(self.current_path))

    def write(self, record: dict):
        if not self.enabled:
            return
        payload = json.dumps(record, ensure_ascii=False) + "\n"
        payload_bytes = len(payload.encode("utf-8"))
        if self.current_file is None or (self.current_bytes + payload_bytes > self.max_bytes and self.current_bytes > 0):
            self._rotate()
        self.current_file.write(payload)
        self.current_file.flush()
        self.current_bytes += payload_bytes

    def close(self):
        if self.current_file:
            self.current_file.close()
            self.current_file = None


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def parse_target_spec(target):
    left, host = target.split("=", 1)
    if ":" in left:
        target_name, group = left.split(":", 1)
    else:
        target_name = left
        group = left
    host = host.strip()
    is_local = host.lower() in LOCAL_TARGET_ALIASES
    display_host = "local" if is_local else host
    return {
        "spec": target,
        "name": target_name.strip(),
        "group": group.strip(),
        "host": host,
        "is_local": is_local,
        "display_host": display_host,
    }


def run_target_command(target_info, command):
    if target_info["is_local"]:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            shell=True,
            executable="/bin/bash",
        )
    return subprocess.run(
        ["ssh", target_info["host"], command],
        check=True,
        capture_output=True,
        text=True,
    )


def init_target_summary(target_info) -> dict:
    return {
        "role": target_info["name"],
        "group": target_info["group"],
        "ssh_host": target_info["display_host"],
        "sample_rounds": 0,
        "successful_rounds": 0,
        "error_rounds": 0,
        "gpu_value_count": 0,
        "gpu_value_sum": 0.0,
        "gpu_util_max": None,
        "memory_value_count": 0,
        "memory_value_sum": 0.0,
        "memory_util_max": None,
        "power_value_count": 0,
        "power_value_sum": 0.0,
        "power_w_max": None,
        "cpu_value_count": 0,
        "cpu_value_sum": 0.0,
        "cpu_util_max": None,
        "errors": [],
    }


def update_metric_stats(summary, key_prefix, values):
    if not values:
        return
    count_key = f"{key_prefix}_value_count"
    sum_key = f"{key_prefix}_value_sum"
    max_key = f"{key_prefix}_util_max"
    summary[count_key] += len(values)
    summary[sum_key] += sum(values)
    current_max = max(values)
    summary[max_key] = current_max if summary[max_key] is None else max(summary[max_key], current_max)


def finalize_target_summary(summary: dict) -> dict:
    gpu_avg = None
    if summary["gpu_value_count"]:
        gpu_avg = round(summary["gpu_value_sum"] / summary["gpu_value_count"], 4)
    mem_avg = None
    if summary["memory_value_count"]:
        mem_avg = round(summary["memory_value_sum"] / summary["memory_value_count"], 4)
    power_avg = None
    if summary["power_value_count"]:
        power_avg = round(summary["power_value_sum"] / summary["power_value_count"], 4)
    cpu_avg = None
    if summary["cpu_value_count"]:
        cpu_avg = round(summary["cpu_value_sum"] / summary["cpu_value_count"], 4)
    return {
        "role": summary["role"],
        "group": summary["group"],
        "ssh_host": summary["ssh_host"],
        "sample_count": summary["successful_rounds"],
        "sample_rounds": summary["sample_rounds"],
        "error_rounds": summary["error_rounds"],
        "gpu_util_avg": gpu_avg,
        "gpu_util_max": round(summary["gpu_util_max"], 4) if summary["gpu_util_max"] is not None else None,
        "memory_util_avg": mem_avg,
        "memory_util_max": round(summary["memory_util_max"], 4) if summary["memory_util_max"] is not None else None,
        "power_w_avg": power_avg,
        "power_w_max": round(summary["power_w_max"], 4) if summary["power_w_max"] is not None else None,
        "cpu_util_avg": cpu_avg,
        "cpu_util_max": round(summary["cpu_util_max"], 4) if summary["cpu_util_max"] is not None else None,
        "errors": summary["errors"],
    }


def build_group_summaries(targets):
    groups = {}
    for target in targets:
        group_name = target.get("group") or target["role"]
        bucket = groups.setdefault(
            group_name,
            {
                "group": group_name,
                "members": [],
                "sample_count": 0,
                "sample_rounds": 0,
                "error_rounds": 0,
                "gpu_sum": 0.0,
                "gpu_count": 0,
                "gpu_util_max": None,
                "memory_sum": 0.0,
                "memory_count": 0,
                "memory_util_max": None,
                "power_sum": 0.0,
                "power_count": 0,
                "power_w_max": None,
                "cpu_sum": 0.0,
                "cpu_count": 0,
                "cpu_util_max": None,
                "errors": [],
            },
        )
        bucket["members"].append(target["role"])
        bucket["sample_count"] += target.get("sample_count", 0) or 0
        bucket["sample_rounds"] += target.get("sample_rounds", 0) or 0
        bucket["error_rounds"] += target.get("error_rounds", 0) or 0
        if target.get("gpu_util_avg") is not None and target.get("sample_count"):
            bucket["gpu_sum"] += target["gpu_util_avg"] * target["sample_count"]
            bucket["gpu_count"] += target["sample_count"]
        if target.get("gpu_util_max") is not None:
            bucket["gpu_util_max"] = target["gpu_util_max"] if bucket["gpu_util_max"] is None else max(bucket["gpu_util_max"], target["gpu_util_max"])
        if target.get("memory_util_avg") is not None and target.get("sample_count"):
            bucket["memory_sum"] += target["memory_util_avg"] * target["sample_count"]
            bucket["memory_count"] += target["sample_count"]
        if target.get("memory_util_max") is not None:
            bucket["memory_util_max"] = target["memory_util_max"] if bucket["memory_util_max"] is None else max(bucket["memory_util_max"], target["memory_util_max"])
        if target.get("power_w_avg") is not None and target.get("sample_count"):
            bucket["power_sum"] += target["power_w_avg"] * target["sample_count"]
            bucket["power_count"] += target["sample_count"]
        if target.get("power_w_max") is not None:
            bucket["power_w_max"] = target["power_w_max"] if bucket["power_w_max"] is None else max(bucket["power_w_max"], target["power_w_max"])
        if target.get("cpu_util_avg") is not None and target.get("sample_count"):
            bucket["cpu_sum"] += target["cpu_util_avg"] * target["sample_count"]
            bucket["cpu_count"] += target["sample_count"]
        if target.get("cpu_util_max") is not None:
            bucket["cpu_util_max"] = target["cpu_util_max"] if bucket["cpu_util_max"] is None else max(bucket["cpu_util_max"], target["cpu_util_max"])
        bucket["errors"].extend(target.get("errors") or [])

    result = []
    for group_name, bucket in groups.items():
        result.append(
            {
                "group": group_name,
                "member_count": len(bucket["members"]),
                "members": bucket["members"],
                "sample_count": bucket["sample_count"],
                "sample_rounds": bucket["sample_rounds"],
                "error_rounds": bucket["error_rounds"],
                "gpu_util_avg": round(bucket["gpu_sum"] / bucket["gpu_count"], 4) if bucket["gpu_count"] else None,
                "gpu_util_max": round(bucket["gpu_util_max"], 4) if bucket["gpu_util_max"] is not None else None,
                "memory_util_avg": round(bucket["memory_sum"] / bucket["memory_count"], 4) if bucket["memory_count"] else None,
                "memory_util_max": round(bucket["memory_util_max"], 4) if bucket["memory_util_max"] is not None else None,
                "power_w_avg": round(bucket["power_sum"] / bucket["power_count"], 4) if bucket["power_count"] else None,
                "power_w_max": round(bucket["power_w_max"], 4) if bucket["power_w_max"] is not None else None,
                "cpu_util_avg": round(bucket["cpu_sum"] / bucket["cpu_count"], 4) if bucket["cpu_count"] else None,
                "cpu_util_max": round(bucket["cpu_util_max"], 4) if bucket["cpu_util_max"] is not None else None,
                "errors": bucket["errors"],
            }
        )
    return result


def sample_once(target_info, remote_command, cpu_command, detail_level):
    started_at = time.time()
    record = {
        "timestamp": started_at,
        "iso_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started_at)),
        "role": target_info["name"],
        "group": target_info["group"],
        "ssh_host": target_info["display_host"],
        "ok": False,
        "duration_seconds": None,
        "gpu_utils": [],
        "memory_utils": [],
        "power_watts": [],
        "cpu_util": None,
    }
    errors = []
    try:
        result = run_target_command(target_info, remote_command)
        payload = json.loads(result.stdout)
        gpu_utils = extract_numbers(payload, {"gpu", "gpu_util", "gpu_utilization", "utilization.gpu"})
        mem_utils = extract_numbers(payload, {"memory", "mem", "memory_util", "memory_utilization", "utilization.memory"})
        power_watts = extract_numbers(
            payload,
            {
                "power",
                "power_w",
                "power_draw",
                "power_draw",
                "average_power",
                "board_power",
                "gpu_power",
            },
        )
        record["ok"] = True
        record["gpu_utils"] = gpu_utils
        record["memory_utils"] = mem_utils
        record["power_watts"] = power_watts
        if detail_level == "raw":
            record["raw"] = payload
    except Exception as exc:  # pragma: no cover - best effort collector
        errors.append(f"gpu:{exc}")
    if cpu_command:
        try:
            cpu_result = run_target_command(target_info, cpu_command)
            cpu_util = parse_cpu_util_value(cpu_result.stdout.strip())
            record["cpu_util"] = cpu_util
            if cpu_util is not None:
                record["ok"] = True
            if detail_level == "raw":
                record["cpu_raw"] = cpu_result.stdout.strip()
        except Exception as exc:  # pragma: no cover - best effort collector
            errors.append(f"cpu:{exc}")
    if errors:
        record["error"] = " | ".join(errors)
    record["duration_seconds"] = round(time.time() - started_at, 4)
    return record


def run_sampling(args, detail_writer):
    target_infos = [parse_target_spec(target) for target in args.ssh_target]
    target_summaries = {target_info["spec"]: init_target_summary(target_info) for target_info in target_infos}
    started_at = time.time()
    wrapped_proc = None
    wrapped_returncode = None
    mode = "fixed_count"
    total_rounds = 0
    stop_deadline = None

    if args.run_command and args.until_pid:
        raise SystemExit("Use only one of --run-command or --until-pid.")
    if args.run_command:
        mode = "wrapped_command"
        wrapped_proc = subprocess.Popen(args.run_command, shell=True)
    elif args.until_pid:
        mode = "follow_pid"
        if not process_exists(args.until_pid):
            raise SystemExit(f"PID {args.until_pid} is not running.")
    elif args.sample_count <= 0:
        raise SystemExit("--sample-count must be > 0 in standalone mode.")

    while True:
        round_started_at = time.time()
        total_rounds += 1
        for target_info in target_infos:
            record = sample_once(target_info, args.remote_command, args.cpu_command, args.detail_level)
            summary = target_summaries[target_info["spec"]]
            summary["sample_rounds"] += 1
            if record["ok"]:
                summary["successful_rounds"] += 1
                update_metric_stats(summary, "gpu", record["gpu_utils"])
                update_metric_stats(summary, "memory", record["memory_utils"])
                update_metric_stats(summary, "power", record["power_watts"])
                if record["cpu_util"] is not None:
                    update_metric_stats(summary, "cpu", [record["cpu_util"]])
            else:
                summary["error_rounds"] += 1
                summary["errors"].append(record.get("error", "unknown error"))
            if args.detail_level != "none":
                detail_writer.write(record)

        if mode == "fixed_count":
            if total_rounds >= args.sample_count:
                break
        elif mode == "wrapped_command":
            if wrapped_proc.poll() is not None and stop_deadline is None:
                wrapped_returncode = wrapped_proc.returncode
                stop_deadline = time.time() + max(args.post_stop_grace_seconds, 0.0)
            if stop_deadline is not None and time.time() >= stop_deadline:
                break
        elif mode == "follow_pid":
            if not process_exists(args.until_pid) and stop_deadline is None:
                stop_deadline = time.time() + max(args.post_stop_grace_seconds, 0.0)
            if stop_deadline is not None and time.time() >= stop_deadline:
                break

        elapsed = time.time() - round_started_at
        sleep_seconds = max(0.0, args.interval_seconds - elapsed)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    finished_at = time.time()
    targets = [finalize_target_summary(target_summaries[target_info["spec"]]) for target_info in target_infos]
    result = {
        "mode": mode,
        "targets": targets,
        "groups": build_group_summaries(targets),
        "interval_seconds": args.interval_seconds,
        "sample_count": total_rounds,
        "detail_level": args.detail_level,
        "detail_files": detail_writer.files,
        "detail_dir": str(detail_writer.detail_dir) if detail_writer.enabled else "",
        "chunk_max_bytes": detail_writer.max_bytes,
        "remote_command": args.remote_command,
        "cpu_command": args.cpu_command,
        "started_at": started_at,
        "ended_at": finished_at,
        "duration_seconds": round(finished_at - started_at, 4),
    }
    if args.run_command:
        result["wrapped_command"] = args.run_command
        result["wrapped_returncode"] = wrapped_returncode
    if args.until_pid:
        result["until_pid"] = args.until_pid
    return result


def main():
    args = parse_args()
    if not args.ssh_target:
        raise SystemExit("At least one --ssh-target is required.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    detail_dir = Path(args.detail_dir) if args.detail_dir else output_path.with_name(f"{output_path.stem}_details")
    chunk_max_bytes = max(1, int(args.chunk_max_gb * 1024 * 1024 * 1024))
    detail_writer = DetailShardWriter(
        detail_dir=detail_dir,
        max_bytes=chunk_max_bytes,
        enabled=args.detail_level != "none",
    )

    try:
        results = run_sampling(args, detail_writer)
    finally:
        detail_writer.close()

    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    if args.run_command:
        raise SystemExit(results.get("wrapped_returncode", 0))


if __name__ == "__main__":
    main()
