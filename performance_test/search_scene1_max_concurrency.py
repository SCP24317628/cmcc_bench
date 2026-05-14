#!/usr/bin/env python3

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCENE_REQUIREMENTS = json.loads((SCRIPT_DIR / "scene_requirements.json").read_text(encoding="utf-8"))
PHASE_REQUEST_MULTIPLIER = {
    "rough": 2,
    "binary": 4,
    "confirm": 5,
}


def load_scene_defaults(scene_name: str) -> dict:
    if scene_name in SCENE_REQUIREMENTS:
        return {"scene_id": scene_name, **SCENE_REQUIREMENTS[scene_name]}
    for scene_id, info in SCENE_REQUIREMENTS.items():
        if scene_name == info["scene_name"]:
            return {"scene_id": scene_id, **info}
    raise KeyError(f"Unknown scene: {scene_name}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Search max passing concurrency under P90 TTFT/TPOT constraints."
    )
    parser.add_argument("--scene-name", required=True, help="Scene id like 4.4.2 or alias like scene1_agent")
    parser.add_argument("--host-ip", required=True)
    parser.add_argument("--host-port", type=int, required=True)
    parser.add_argument("--model-name", default="")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--start-batch-size", type=int, default=1)
    parser.add_argument("--max-batch-size", type=int, default=512)
    parser.add_argument("--request-rate", type=float, default=0)
    parser.add_argument("--min-request-count", type=int, default=30)
    parser.add_argument("--dataset-type", choices=["string", "tokenid"], default="tokenid")
    parser.add_argument("--summarizer", choices=["stable_stage", "default_perf"], default="stable_stage")
    parser.add_argument("--input-len", type=int)
    parser.add_argument("--output-len", type=int)
    parser.add_argument("--ttft-limit-ms", type=float)
    parser.add_argument("--tpot-limit-ms", type=float)
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--disable-ignore-eos", action="store_true")
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--parallel-strategy", default="")
    parser.add_argument("--pd-ratio", default="")
    parser.add_argument("--tp-size", type=int, default=0)
    parser.add_argument("--ep-size", type=int, default=0)
    parser.add_argument("--pp-size", type=int, default=0)
    parser.add_argument("--dp-size", type=int, default=0)
    parser.add_argument("--etp-size", type=int, default=0)
    parser.add_argument("--total-servers", type=int, default=1)
    parser.add_argument("--prefill-servers", type=int, default=0)
    parser.add_argument("--decoder-servers", type=int, default=0)
    parser.add_argument("--total-cards", type=int, default=1)
    parser.add_argument("--prefill-cards", type=int, default=0)
    parser.add_argument("--decoder-cards", type=int, default=0)
    parser.add_argument("--resource-ssh-target", action="append", default=[])
    parser.add_argument("--resource-sample-count", type=int, default=3)
    parser.add_argument("--resource-interval-seconds", type=float, default=5.0)
    parser.add_argument("--confirm-rounds", type=int, default=1)
    parser.add_argument(
        "--live-output",
        action="store_true",
        help="实时打印每个试点的 AISBench 输出，同时保留日志到 summary.json",
    )
    return parser.parse_args()


def request_count_for_phase_with_min(phase: str, batch_size: int, min_request_count: int) -> int:
    multiplier = PHASE_REQUEST_MULTIPLIER.get(phase, 1)
    return max(min_request_count, multiplier * batch_size)


def normalize_metric_value(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    for suffix in ("ms", "token/s", "req/s"):
        text = text.replace(suffix, "")
    try:
        return float(text.strip())
    except ValueError:
        return None


def find_key(row, candidates):
    lowered = {str(k).strip().lower(): k for k in row.keys()}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def metric_value(metrics: dict, *candidates):
    for key in candidates:
        if key in metrics and metrics[key] is not None:
            return metrics[key]
    return None


def parse_perf_csv(csv_path: Path) -> dict:
    metrics = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name_key = find_key(row, {"performance parameters", "metric"})
            if not name_key:
                continue
            stage_key = find_key(row, {"stage"})
            metric_name = str(row[name_key]).strip()
            stage_name = str(row.get(stage_key, "")).strip().lower() if stage_key else ""
            if not metric_name:
                continue
            for alias, field_names in {
                "average": {"average", "avg"},
                "median": {"median", "p50"},
                "p90": {"p90"},
                "p95": {"p95"},
                "p99": {"p99"},
                "min": {"min"},
                "max": {"max"},
            }.items():
                value_key = find_key(row, field_names)
                if not value_key:
                    continue
                value = normalize_metric_value(row[value_key])
                if stage_name:
                    metrics[f"{metric_name}.{stage_name}.{alias}"] = value
                    if stage_name == "stable":
                        metrics[f"{metric_name}.{alias}"] = value
                else:
                    metrics[f"{metric_name}.{alias}"] = value
    return metrics


def parse_common_json(json_path: Path) -> dict:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    metrics = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                for stage, stage_value in value.items():
                    normalized = normalize_metric_value(stage_value)
                    metrics[f"{key}.{stage}"] = normalized
                    if stage == "stable":
                        metrics[key] = normalized
            else:
                metrics[key] = normalize_metric_value(value)
        return metrics

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            metric_name = item.get("Common Metric") or item.get("metric")
            stage_name = item.get("Stage") or item.get("stage")
            value = item.get("Value") if "Value" in item else item.get("value")
            if not metric_name:
                continue
            normalized = normalize_metric_value(value)
            if stage_name:
                stage_name = str(stage_name).strip().lower()
                metrics[f"{metric_name}.{stage_name}"] = normalized
                if stage_name == "stable":
                    metrics[str(metric_name)] = normalized
            else:
                metrics[str(metric_name)] = normalized
    return metrics


def parse_run_artifacts(meta: dict) -> dict:
    metrics = {}
    csv_path = Path(meta["csv"]) if meta.get("csv") else None
    json_path = Path(meta["json"]) if meta.get("json") else None
    if csv_path and csv_path.exists():
        metrics.update(parse_perf_csv(csv_path))
    if json_path and json_path.exists():
        metrics.update(parse_common_json(json_path))
    return metrics


def evaluate_pass_status(metrics: dict, ttft_limit_ms: float | None, tpot_limit_ms: float | None) -> dict:
    ttft_p90_ms = metric_value(metrics, "TTFT.stable.p90", "TTFT.p90")
    tpot_p90_ms = metric_value(metrics, "TPOT.stable.p90", "TPOT.p90")
    pass_ttft = ttft_limit_ms is None or (ttft_p90_ms is not None and ttft_p90_ms <= ttft_limit_ms)
    pass_tpot = tpot_limit_ms is None or (tpot_p90_ms is not None and tpot_p90_ms <= tpot_limit_ms)
    return {
        "ttft_p90_ms": ttft_p90_ms,
        "tpot_p90_ms": tpot_p90_ms,
        "pass_ttft": pass_ttft,
        "pass_tpot": pass_tpot,
    }


def run_point(args, scene, batch_size: int, phase: str, attempt: int = 1) -> dict:
    request_count = request_count_for_phase_with_min(phase, batch_size, args.min_request_count)
    point_name = f"{phase}_b{batch_size}"
    if args.confirm_rounds > 1 or attempt > 1:
        point_name = f"{point_name}_r{attempt}"
    point_root = Path(args.work_root) / "trials" / point_name
    env = os.environ.copy()
    env.update(
        {
            "HOST_IP": args.host_ip,
            "HOST_PORT": str(args.host_port),
            "MODEL_NAME": args.model_name,
            "MODEL_PATH": args.model_path,
            "REQUEST_COUNT": str(request_count),
            "BATCH_SIZE": str(batch_size),
            "REQUEST_RATE": str(args.request_rate),
            "INPUT_LEN": str(args.input_len or scene["input_len"]),
            "OUTPUT_LEN": str(args.output_len or scene["output_len"]),
            "DATASET_TYPE": args.dataset_type,
            "ENABLE_THINKING": "true" if args.enable_thinking else "false",
            "USE_MAX_COMPLETION_TOKENS": "true",
            "IGNORE_EOS": "false" if args.disable_ignore_eos else "true",
            "SUMMARIZER": args.summarizer,
            "WORK_DIR": str(point_root),
            "MODEL_ABBR": f"cmcc-minimax25-b{batch_size}",
            "DATASET_ABBR": f"{scene['scene_name']}_b{batch_size}",
        }
    )

    cmd = [str(SCRIPT_DIR / "run_synthetic_perf_smoke.sh")]
    if args.live_output:
        print(
            f"\n===== START {point_name} "
            f"(batch_size={batch_size}, request_count={request_count}, "
            f"input_len={args.input_len or scene['input_len']}, output_len={args.output_len or scene['output_len']}) =====",
            flush=True,
        )
        proc = subprocess.Popen(
            cmd,
            cwd=str(SCRIPT_DIR),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        combined_output_lines = []
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            combined_output_lines.append(line)
        return_code = proc.wait()
        stdout_text = "".join(combined_output_lines)
        stderr_text = ""
        print(f"===== END {point_name} (return_code={return_code}) =====\n", flush=True)
    else:
        proc = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            env=env,
            text=True,
            capture_output=True,
        )
        return_code = proc.returncode
        stdout_text = proc.stdout
        stderr_text = proc.stderr

    point = {
        "phase": phase,
        "attempt": attempt,
        "point_name": point_name,
        "batch_size": batch_size,
        "request_count": request_count,
        "request_rate": args.request_rate,
        "input_len": args.input_len or scene["input_len"],
        "output_len": args.output_len or scene["output_len"],
        "return_code": return_code,
        "stdout": stdout_text,
        "stderr": stderr_text,
    }
    if return_code != 0:
        point.update(
            {
                "metrics": {},
                "pass_ttft": False,
                "pass_tpot": False,
                "passed": False,
            }
        )
        return point

    last_line = next(
        (line for line in reversed(stdout_text.splitlines()) if line.strip().startswith("{")),
        "",
    )
    if last_line:
        artifacts = json.loads(last_line)
        point["artifacts"] = artifacts
        point["metrics"] = parse_run_artifacts(artifacts)
    else:
        point["metrics"] = {}

    decision = evaluate_pass_status(
        point["metrics"],
        args.ttft_limit_ms if args.ttft_limit_ms is not None else scene["ttft_limit_ms"],
        args.tpot_limit_ms if args.tpot_limit_ms is not None else scene["tpot_limit_ms"],
    )
    point.update(decision)
    point["passed"] = point["return_code"] == 0 and point["pass_ttft"] and point["pass_tpot"]
    point["actual_concurrency"] = metric_value(
        point["metrics"],
        "Concurrency.stable",
        "Concurrency",
    )
    return point


def rough_search(args, scene) -> dict:
    points = []
    last_good = None
    first_bad = None
    batch_size = args.start_batch_size
    while batch_size <= args.max_batch_size:
        point = run_point(args, scene, batch_size, phase="rough")
        points.append(point)
        if point["passed"]:
            last_good = point
            batch_size *= 2
            continue
        first_bad = point
        break
    return {
        "points": points,
        "last_good": last_good,
        "first_bad": first_bad,
    }


def binary_search(args, scene, last_good: dict | None, first_bad: dict | None) -> dict:
    if not last_good or not first_bad:
        return {
            "points": [],
            "best_good": last_good,
            "first_bad": first_bad,
        }

    pass_points = {last_good["batch_size"]: last_good}
    fail_points = {first_bad["batch_size"]: first_bad}
    points = []
    low = last_good["batch_size"]
    high = first_bad["batch_size"]

    while high - low > 1:
        mid = (low + high) // 2
        point = run_point(args, scene, mid, phase="binary")
        points.append(point)
        if point["passed"]:
            pass_points[mid] = point
            low = mid
        else:
            fail_points[mid] = point
            high = mid

    best_good_batch_size = max(pass_points)
    first_bad_batch_size = min(batch_size for batch_size in fail_points if batch_size > best_good_batch_size)
    return {
        "points": points,
        "best_good": pass_points[best_good_batch_size],
        "first_bad": fail_points[first_bad_batch_size],
    }


def confirm_points(args, scene, best_good: dict | None, first_bad: dict | None) -> dict:
    if not best_good:
        return {
            "points": [],
            "final_result": None,
        }

    candidate_batch_sizes = [best_good["batch_size"]]
    if first_bad:
        maybe_batch_size = first_bad["batch_size"] - 1
        if maybe_batch_size >= 1 and maybe_batch_size not in candidate_batch_sizes:
            candidate_batch_sizes.append(maybe_batch_size)

    points = []
    confirmed = {}
    for batch_size in candidate_batch_sizes:
        attempts = []
        for attempt in range(1, args.confirm_rounds + 1):
            point = run_point(args, scene, batch_size, phase="confirm", attempt=attempt)
            points.append(point)
            attempts.append(point)
        if attempts and all(point["passed"] for point in attempts):
            confirmed[batch_size] = attempts[-1]

    final_batch_size = max(confirmed) if confirmed else None
    return {
        "points": points,
        "final_result": confirmed.get(final_batch_size),
    }


def sample_resources(args, output_file: Path) -> dict | None:
    if not args.resource_ssh_target:
        return None
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "sample_gpu_resources.py"),
        "--output",
        str(output_file),
        "--sample-count",
        str(args.resource_sample_count),
        "--interval-seconds",
        str(args.resource_interval_seconds),
    ]
    for target in args.resource_ssh_target:
        cmd.extend(["--ssh-target", target])
    proc = subprocess.run(cmd, cwd=str(SCRIPT_DIR), text=True, capture_output=True)
    if proc.returncode != 0 or not output_file.exists():
        return {"error": proc.stderr or proc.stdout}
    return json.loads(output_file.read_text(encoding="utf-8"))


def aggregate_resource_metrics(resource_payload: dict | None) -> dict:
    if not resource_payload or resource_payload.get("error"):
        return {"gpu_util_avg": None, "memory_util_avg": None}
    gpu_values = [
        target["gpu_util_avg"]
        for target in resource_payload.get("targets", [])
        if target.get("gpu_util_avg") is not None
    ]
    mem_values = [
        target["memory_util_avg"]
        for target in resource_payload.get("targets", [])
        if target.get("memory_util_avg") is not None
    ]
    return {
        "gpu_util_avg": round(statistics.mean(gpu_values), 4) if gpu_values else None,
        "memory_util_avg": round(statistics.mean(mem_values), 4) if mem_values else None,
    }


def compute_throughput_metrics(summary: dict, final_result: dict | None) -> dict:
    metrics = (final_result or {}).get("metrics", {})
    total_servers = summary.get("total_servers") or 1
    total_cards = summary.get("total_cards") or 1
    decoder_cards = summary.get("decoder_cards") or total_cards

    request_throughput = metric_value(metrics, "Request Throughput.stable", "Request Throughput")
    actual_concurrency = metric_value(metrics, "Concurrency.stable", "Concurrency")
    total_token_throughput = metric_value(metrics, "Total Token Throughput.stable", "Total Token Throughput")
    input_token_throughput = metric_value(metrics, "Input Token Throughput.stable", "Input Token Throughput")
    output_token_throughput = metric_value(metrics, "Output Token Throughput.stable", "Output Token Throughput")

    return {
        "Actual Concurrency": actual_concurrency,
        "Request Throughput (req/s)": request_throughput,
        "Input Token Throughput (tok/s)": input_token_throughput,
        "Output Token Throughput (tok/s)": output_token_throughput,
        "Total Token Throughput (tok/s)": total_token_throughput,
        "Single Server Throughput (tok/s)": round(total_token_throughput / total_servers, 6)
        if total_token_throughput is not None
        else None,
        "Single Card Throughput (tok/s)": round(total_token_throughput / total_cards, 6)
        if total_token_throughput is not None
        else None,
        "Decode Single Card Throughput (tok/s)": round(output_token_throughput / decoder_cards, 6)
        if output_token_throughput is not None
        else None,
    }


def select_clean_summary_result(summary: dict) -> tuple[dict | None, str]:
    final_result = summary.get("final_result")
    if final_result:
        return final_result, "pass"

    confirm_points = (summary.get("confirm_result") or {}).get("points") or []
    if confirm_points:
        chosen = max(
            confirm_points,
            key=lambda point: (
                point.get("batch_size") or 0,
                point.get("attempt") or 0,
            ),
        )
        return chosen, "pass"

    binary_best = (summary.get("binary_result") or {}).get("best_good")
    if binary_best:
        return binary_best, "pass"

    rough_best = (summary.get("rough_result") or {}).get("last_good")
    if rough_best:
        return rough_best, "pass"

    return None, "no_result"


def write_clean_summary_csv(output_path: Path, summary: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_result, status = select_clean_summary_result(summary)
    resource_metrics = summary.get("resource_metrics", {})
    if not final_result:
        row = {
            "Scene ID": summary["scene_id"],
            "Scene Name": summary["scene_name"],
            "Status": status,
        }
    else:
        metrics = final_result.get("metrics", {})
        artifacts = final_result.get("artifacts", {})
        row = {
            "Scene ID": summary["scene_id"],
            "Scene Name": summary["scene_name"],
            "Display Name": summary["display_name"],
            "Input Len": summary["input_len"],
            "Output Len": summary["output_len"],
            "Preset BS": final_result.get("batch_size"),
            "Actual Concurrency": compute_throughput_metrics(summary, final_result)["Actual Concurrency"],
            "Request Count": final_result.get("request_count"),
            "Request Rate": summary["request_rate"],
            "PD Ratio": summary["pd_ratio"],
            "Parallel Strategy": summary["parallel_strategy"],
            "TP Size": summary["tp_size"],
            "EP Size": summary["ep_size"],
            "PP Size": summary["pp_size"],
            "DP Size": summary["dp_size"],
            "ETP Size": summary["etp_size"],
            "Total Servers": summary["total_servers"],
            "Prefill Servers": summary["prefill_servers"],
            "Decoder Servers": summary["decoder_servers"],
            "Total Cards": summary["total_cards"],
            "Prefill Cards": summary["prefill_cards"],
            "Decoder Cards": summary["decoder_cards"],
            "TTFT Mean (ms)": metric_value(metrics, "TTFT.stable.average", "TTFT.average"),
            "TTFT P50 (ms)": metric_value(metrics, "TTFT.stable.median", "TTFT.median"),
            "TTFT P90 (ms)": metric_value(metrics, "TTFT.stable.p90", "TTFT.p90"),
            "TTFT P99 (ms)": metric_value(metrics, "TTFT.stable.p99", "TTFT.p99"),
            "TPOT Mean (ms)": metric_value(metrics, "TPOT.stable.average", "TPOT.average"),
            "TPOT P50 (ms)": metric_value(metrics, "TPOT.stable.median", "TPOT.median"),
            "TPOT P90 (ms)": metric_value(metrics, "TPOT.stable.p90", "TPOT.p90"),
            "TPOT P99 (ms)": metric_value(metrics, "TPOT.stable.p99", "TPOT.p99"),
            "ITL Mean (ms)": metric_value(metrics, "ITL.stable.average", "ITL.average"),
            "ITL P50 (ms)": metric_value(metrics, "ITL.stable.median", "ITL.median"),
            "ITL P90 (ms)": metric_value(metrics, "ITL.stable.p90", "ITL.p90"),
            "ITL P99 (ms)": metric_value(metrics, "ITL.stable.p99", "ITL.p99"),
            "E2EL Mean (ms)": metric_value(metrics, "E2EL.stable.average", "E2EL.average"),
            "E2EL P50 (ms)": metric_value(metrics, "E2EL.stable.median", "E2EL.median"),
            "E2EL P90 (ms)": metric_value(metrics, "E2EL.stable.p90", "E2EL.p90"),
            "E2EL P99 (ms)": metric_value(metrics, "E2EL.stable.p99", "E2EL.p99"),
            "Request Throughput (req/s)": compute_throughput_metrics(summary, final_result)["Request Throughput (req/s)"],
            "Input Token Throughput (tok/s)": compute_throughput_metrics(summary, final_result)["Input Token Throughput (tok/s)"],
            "Output Token Throughput (tok/s)": compute_throughput_metrics(summary, final_result)["Output Token Throughput (tok/s)"],
            "Total Token Throughput (tok/s)": compute_throughput_metrics(summary, final_result)["Total Token Throughput (tok/s)"],
            "Single Server Throughput (tok/s)": compute_throughput_metrics(summary, final_result)["Single Server Throughput (tok/s)"],
            "Single Card Throughput (tok/s)": compute_throughput_metrics(summary, final_result)["Single Card Throughput (tok/s)"],
            "Decode Single Card Throughput (tok/s)": compute_throughput_metrics(summary, final_result)["Decode Single Card Throughput (tok/s)"],
            "GPU Util Avg": resource_metrics.get("gpu_util_avg"),
            "Memory Util Avg": resource_metrics.get("memory_util_avg"),
            "Result Dir": artifacts.get("experiment_dir", ""),
            "CSV Path": artifacts.get("csv", ""),
            "JSON Path": artifacts.get("json", ""),
            "HTML Path": artifacts.get("html", ""),
            "Status": status,
        }

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def main():
    args = parse_args()
    scene = load_scene_defaults(args.scene_name)
    ttft_limit_ms = args.ttft_limit_ms if args.ttft_limit_ms is not None else scene["ttft_limit_ms"]
    tpot_limit_ms = args.tpot_limit_ms if args.tpot_limit_ms is not None else scene["tpot_limit_ms"]
    work_root = Path(args.work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    rough_result = rough_search(args, scene)
    best_good = rough_result["last_good"]
    first_bad = rough_result["first_bad"]

    if best_good and first_bad and first_bad["batch_size"] - best_good["batch_size"] > 1:
        binary_result = binary_search(args, scene, best_good, first_bad)
        best_good = binary_result["best_good"]
        first_bad = binary_result["first_bad"]
    else:
        binary_result = {
            "points": [],
            "best_good": best_good,
            "first_bad": first_bad,
        }

    confirm_result = confirm_points(args, scene, best_good, first_bad)
    final_result = confirm_result["final_result"]

    resource_payload = None
    resource_metrics = {"gpu_util_avg": None, "memory_util_avg": None}
    if final_result:
        resource_payload = sample_resources(args, work_root / "resource_samples.json")
        resource_metrics = aggregate_resource_metrics(resource_payload)
        final_result["resource_metrics"] = resource_metrics
        if resource_payload:
            final_result["resource_samples"] = resource_payload

    summary = {
        "scene_id": scene["scene_id"],
        "scene_name": scene["scene_name"],
        "display_name": scene["display_name"],
        "input_len": args.input_len or scene["input_len"],
        "output_len": args.output_len or scene["output_len"],
        "ttft_limit_ms": ttft_limit_ms,
        "tpot_limit_ms": tpot_limit_ms,
        "request_rate": args.request_rate,
        "dataset_type": args.dataset_type,
        "summarizer": args.summarizer,
        "parallel_strategy": args.parallel_strategy,
        "pd_ratio": args.pd_ratio,
        "tp_size": args.tp_size,
        "ep_size": args.ep_size,
        "pp_size": args.pp_size,
        "dp_size": args.dp_size,
        "etp_size": args.etp_size,
        "total_servers": args.total_servers,
        "prefill_servers": args.prefill_servers,
        "decoder_servers": args.decoder_servers,
        "total_cards": args.total_cards,
        "prefill_cards": args.prefill_cards,
        "decoder_cards": args.decoder_cards,
        "rough_result": rough_result,
        "binary_result": binary_result,
        "confirm_result": confirm_result,
        "best_good_batch_size": best_good["batch_size"] if best_good else None,
        "first_bad_batch_size": first_bad["batch_size"] if first_bad else None,
        "final_result": final_result,
        "resource_metrics": resource_metrics,
        "resource_samples": resource_payload,
    }

    summary_path = work_root / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    clean_csv_path = work_root / f"{scene['scene_name']}_summary_clean.csv"
    write_clean_summary_csv(clean_csv_path, summary)
    print(summary_path)
    print(clean_csv_path)


if __name__ == "__main__":
    main()
