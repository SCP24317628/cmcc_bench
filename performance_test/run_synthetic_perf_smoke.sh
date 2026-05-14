#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CMCC_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
BENCHMARK_ROOT="${AISBENCH_ROOT:-${CMCC_ROOT}/benchmark}"
PYTHON_BIN="${AISBENCH_PYTHON_BIN:-}"
CONDA_PY="${CMCC_ROOT}/miniconda3/envs/ais_bench/bin/python"
ACTIVE_VENV_PY="${VIRTUAL_ENV:-}/bin/python"

if [[ -n "${AISBENCH_REPO:-}" ]]; then
  REPO_CANDIDATE="${AISBENCH_REPO}"
elif [[ -d "${BENCHMARK_ROOT}/ais_bench/benchmark" && -f "${BENCHMARK_ROOT}/setup.py" ]]; then
  # benchmark/ itself is the AISBench repo root in the current cmcc_bench layout.
  REPO_CANDIDATE="${BENCHMARK_ROOT}"
elif [[ -d "${BENCHMARK_ROOT}/ais_bench/ais_bench/benchmark" ]]; then
  # Backward-compatible layout: benchmark/ais_bench is the repo root.
  REPO_CANDIDATE="${BENCHMARK_ROOT}/ais_bench"
else
  REPO_CANDIDATE="${BENCHMARK_ROOT}"
fi

AISBENCH_REPO="${REPO_CANDIDATE}"
BOOTSTRAP_SCRIPT="${BENCHMARK_ROOT}/bootstrap_aisbench.sh"
INSTALL_SCRIPT="${BENCHMARK_ROOT}/install_aisbench_env.sh"
VENV_PY="${BENCHMARK_ROOT}/ais_bench/bin/python"
LEGACY_VENV_PY="${BENCHMARK_ROOT}/.venv/bin/python"
OVERLAY_DIR="${AISBENCH_OVERLAY:-${SCRIPT_DIR}/aisbench_overlay}"
PY_SITE_PACKAGES="${AISBENCH_PY_SITE:-${SCRIPT_DIR}/.aisbench-py}"
USE_LITE_AISBENCH="${USE_LITE_AISBENCH:-false}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}"
AISBENCH_SOURCE_DIR=""

HOST_IP="${HOST_IP:?HOST_IP is required}"
HOST_PORT="${HOST_PORT:?HOST_PORT is required}"
MODEL_NAME="${MODEL_NAME:-}"
MODEL_PATH="${MODEL_PATH:?MODEL_PATH is required}"
REQUEST_COUNT="${REQUEST_COUNT:-4}"
BATCH_SIZE="${BATCH_SIZE:-1}"
REQUEST_RATE="${REQUEST_RATE:-0}"
INPUT_LEN="${INPUT_LEN:?INPUT_LEN is required}"
OUTPUT_LEN="${OUTPUT_LEN:?OUTPUT_LEN is required}"
DATASET_TYPE="${DATASET_TYPE:-tokenid}"
ENABLE_THINKING="${ENABLE_THINKING:-false}"
USE_MAX_COMPLETION_TOKENS="${USE_MAX_COMPLETION_TOKENS:-true}"
IGNORE_EOS="${IGNORE_EOS:-true}"
SUMMARIZER="${SUMMARIZER:-stable_stage}"
MODEL_ABBR="${MODEL_ABBR:-cmcc-minimax25-b${BATCH_SIZE}}"
DATASET_ABBR="${DATASET_ABBR:-case_${INPUT_LEN}_${OUTPUT_LEN}_b${BATCH_SIZE}_r${REQUEST_COUNT}_${DATASET_TYPE}}"
WORK_DIR="${WORK_DIR:-${CMCC_ROOT}/outputs/${DATASET_ABBR}}"
CONFIG_FILE="${CONFIG_FILE:-${WORK_DIR}/config.py}"
PRESSURE="${PRESSURE:-false}"
PRESSURE_TIME="${PRESSURE_TIME:-30}"
FORCE_BOOTSTRAP="${FORCE_BOOTSTRAP:-false}"
FORCE_INSTALL="${FORCE_INSTALL:-false}"
API_KEY="${API_KEY:-}"
URL="${URL:-}"
TEMPERATURE="${TEMPERATURE:-0.01}"
RETRY="${RETRY:-2}"
TRUST_REMOTE_CODE="${TRUST_REMOTE_CODE:-false}"
PREFIX_LEN="${PREFIX_LEN:-0}"

if [[ -n "${PYTHON_BIN}" ]]; then
  :
elif [[ -x "${ACTIVE_VENV_PY}" ]]; then
  PYTHON_BIN="${ACTIVE_VENV_PY}"
elif command -v python >/dev/null 2>&1 && python - <<'PY' >/dev/null 2>&1
import ais_bench  # noqa: F401
PY
then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1 && python3 - <<'PY' >/dev/null 2>&1
import ais_bench  # noqa: F401
PY
then
  PYTHON_BIN="python3"
elif [[ -x "${CONDA_PY}" ]]; then
  PYTHON_BIN="${CONDA_PY}"
elif [[ -x "${VENV_PY}" ]]; then
  PYTHON_BIN="${VENV_PY}"
elif [[ -x "${LEGACY_VENV_PY}" ]]; then
  PYTHON_BIN="${LEGACY_VENV_PY}"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

if [[ -d "${AISBENCH_REPO}/ais_bench/benchmark" ]]; then
  AISBENCH_SOURCE_DIR="${AISBENCH_REPO}"
elif [[ -d "${AISBENCH_REPO}/ais_bench/ais_bench/benchmark" ]]; then
  AISBENCH_SOURCE_DIR="${AISBENCH_REPO}/ais_bench"
fi

if [[ "${FORCE_BOOTSTRAP}" == "true" ]]; then
  if [[ -x "${BOOTSTRAP_SCRIPT}" || -f "${BOOTSTRAP_SCRIPT}" ]]; then
    bash "${BOOTSTRAP_SCRIPT}"
  else
    echo "bootstrap_aisbench.sh not found under ${BENCHMARK_ROOT}, skip FORCE_BOOTSTRAP." >&2
  fi
fi

if [[ -f "${BENCHMARK_ROOT}/ais_bench/pyvenv.cfg" && ! -d "${BENCHMARK_ROOT}/ais_bench/benchmark" ]]; then
  echo "Detected a virtualenv at ${BENCHMARK_ROOT}/ais_bench, which shadows the AISBench source package directory." >&2
  echo "The repo expects source files under ${BENCHMARK_ROOT}/ais_bench/benchmark, but that path is currently occupied by the venv." >&2
  echo "Please recreate the virtualenv in a different path (for example: ${BENCHMARK_ROOT}/.venv or ${CMCC_ROOT}/.venv_aisbench)." >&2
  exit 1
fi

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import ais_bench  # noqa: F401
PY
then
  if [[ -n "${AISBENCH_SOURCE_DIR}" ]]; then
    echo "Warning: current python (${PYTHON_BIN}) cannot import installed ais_bench, fallback to source tree via PYTHONPATH." >&2
  elif [[ -x "${BOOTSTRAP_SCRIPT}" || -f "${BOOTSTRAP_SCRIPT}" ]]; then
    bash "${BOOTSTRAP_SCRIPT}"
    if [[ -d "${AISBENCH_REPO}/ais_bench/benchmark" ]]; then
      AISBENCH_SOURCE_DIR="${AISBENCH_REPO}"
    elif [[ -d "${AISBENCH_REPO}/ais_bench/ais_bench/benchmark" ]]; then
      AISBENCH_SOURCE_DIR="${AISBENCH_REPO}/ais_bench"
    fi
  else
    echo "Warning: current python (${PYTHON_BIN}) cannot import ais_bench before run; continue and let runtime decide." >&2
  fi
fi

if [[ "${FORCE_INSTALL}" == "true" ]]; then
  if [[ -x "${INSTALL_SCRIPT}" || -f "${INSTALL_SCRIPT}" ]]; then
    bash "${INSTALL_SCRIPT}"
  else
    echo "install_aisbench_env.sh not found under ${BENCHMARK_ROOT}, skip FORCE_INSTALL." >&2
  fi
fi

mkdir -p "${WORK_DIR}"

if [[ "${USE_LITE_AISBENCH}" == "true" ]]; then
  mkdir -p "${PY_SITE_PACKAGES}"
  if ! PYTHONPATH="${OVERLAY_DIR}:${PY_SITE_PACKAGES}:${AISBENCH_REPO}" "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import mmengine
import datasets
import tabulate
import aiohttp
import janus
import numpy
import pandas
import plotly
import prettytable
import requests
import rich
import PIL
import openai
PY
  then
    "${PYTHON_BIN}" -m pip install --target "${PY_SITE_PACKAGES}" \
      -i "${PIP_INDEX_URL}" --trusted-host "${PIP_TRUSTED_HOST}" \
      "mmengine-lite" \
      "datasets>=2.12.0,<=3.6.0" \
      "requests>=2.31.0" \
      "aiohttp" \
      "janus" \
      "numpy>=1.23.4,<2.0.0" \
      "pandas" \
      "plotly" \
      "prettytable" \
      "tabulate" \
      "retrying" \
      "rich" \
      "tqdm>=4.64.1" \
      "Pillow==11.2.1" \
      "openai"
  fi
fi

"${PYTHON_BIN}" "${SCRIPT_DIR}/generate_synthetic_perf_config.py" \
  --output-config "${CONFIG_FILE}" \
  --host-ip "${HOST_IP}" \
  --host-port "${HOST_PORT}" \
  --model-name "${MODEL_NAME}" \
  --model-path "${MODEL_PATH}" \
  --api-key "${API_KEY}" \
  --url "${URL}" \
  --request-count "${REQUEST_COUNT}" \
  --batch-size "${BATCH_SIZE}" \
  --request-rate "${REQUEST_RATE}" \
  --input-len "${INPUT_LEN}" \
  --output-len "${OUTPUT_LEN}" \
  --dataset-type "${DATASET_TYPE}" \
  --summarizer "${SUMMARIZER}" \
  --enable-thinking "${ENABLE_THINKING}" \
  --use-max-completion-tokens "${USE_MAX_COMPLETION_TOKENS}" \
  --ignore-eos "${IGNORE_EOS}" \
  --trust-remote-code "${TRUST_REMOTE_CODE}" \
  --temperature "${TEMPERATURE}" \
  --retry "${RETRY}" \
  --prefix-len "${PREFIX_LEN}" \
  --model-abbr "${MODEL_ABBR}" \
  --dataset-abbr "${DATASET_ABBR}"

if [[ "${USE_LITE_AISBENCH}" == "true" ]]; then
  if [[ -n "${AISBENCH_SOURCE_DIR}" ]]; then
    export PYTHONPATH="${OVERLAY_DIR}:${PY_SITE_PACKAGES}:${AISBENCH_SOURCE_DIR}:${PYTHONPATH:-}"
  else
    export PYTHONPATH="${OVERLAY_DIR}:${PY_SITE_PACKAGES}:${PYTHONPATH:-}"
  fi
else
  if [[ -n "${AISBENCH_SOURCE_DIR}" ]]; then
    export PYTHONPATH="${AISBENCH_SOURCE_DIR}:${PYTHONPATH:-}"
  fi
fi
CMD=("${PYTHON_BIN}" -m ais_bench.benchmark.cli.main "${CONFIG_FILE}" --mode perf --summarizer "${SUMMARIZER}" --work-dir "${WORK_DIR}" --debug)
if [[ "${PRESSURE}" == "true" ]]; then
  CMD+=(--pressure --pressure-time "${PRESSURE_TIME}")
fi

"${CMD[@]}"

"${PYTHON_BIN}" - <<'PY' "${WORK_DIR}"
import json
import sys
from pathlib import Path

work_dir = Path(sys.argv[1])
exp_dirs = sorted([p for p in work_dir.iterdir() if p.is_dir()])
if not exp_dirs:
    raise SystemExit("No AISBench experiment directory created.")

latest = exp_dirs[-1]
patterns = [
    "performance/**/*.csv",
    "performance/**/*.json",
    "performance/**/*.html",
    "performances/**/*.csv",
    "performances/**/*.json",
    "performances/**/*.html",
]
artifacts = {"experiment_dir": str(latest), "csv": "", "json": "", "html": ""}
for pattern in patterns:
    for path in latest.glob(pattern):
        if path.name.endswith("_details.json") or path.name.endswith("_details.h5"):
            continue
        suffix = path.suffix.lower()
        if suffix == ".csv" and not artifacts["csv"]:
            artifacts["csv"] = str(path)
        elif suffix == ".json" and not artifacts["json"]:
            artifacts["json"] = str(path)
        elif suffix == ".html" and not artifacts["html"]:
            artifacts["html"] = str(path)

print(json.dumps(artifacts, ensure_ascii=False))
PY
