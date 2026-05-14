# CMCC AISBench 测试脚本

本目录用于按 `RequirementDescription.txt` 和 `CMCC_BENCH_Transfer_Guide.md` 的口径，基于 AISBench 对 MiniMax M2.5 OpenAI 兼容服务做性能测试。

## 目录说明

- `scene_requirements.json`
  - 场景参数基表，覆盖 `4.4.2 ~ 4.4.7`。
- `generate_synthetic_perf_config.py`
  - 生成 AISBench 自定义 synthetic 配置。
  - 支持 `string` 和 `tokenid`。
  - 支持 `enable_thinking=false`、`max_completion_tokens`、`ignore_eos=true`。
- `run_synthetic_perf_smoke.sh`
  - 单点 smoke 入口。
  - 自动生成配置并调用 AISBench `--mode perf`。
- `search_scene1_max_concurrency.py`
  - 在 TTFT/TPOT 约束下搜索最大可通过并发。
  - 输出 `summary.json` 和 `<scene>_summary_clean.csv`。
- `sample_gpu_resources.py`
  - 通过 SSH 调 `mthreads-gmi` 采样显存和 GPU 利用率。

## 依赖准备

本目录默认依赖仓库根目录下的 `benchmark/` 作为 AISBench 上游源码目录。
如果你是从 GitHub 拉下来的本项目，请先在 `cmcc_bench` 根目录执行：

```bash
git clone https://github.com/AISBench/benchmark.git benchmark
cd benchmark
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e . --use-pep517
```

如果 API 相关依赖缺失，再补：

```bash
pip install -r requirements/api.txt
```

## Smoke 示例

```bash
cd /data/10.121.36.6/data/bohuai/release/cmcc_bench/performance_test

HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME= \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
REQUEST_COUNT=4 \
BATCH_SIZE=1 \
REQUEST_RATE=0 \
INPUT_LEN=4096 \
OUTPUT_LEN=1000 \
DATASET_TYPE=tokenid \
ENABLE_THINKING=false \
USE_MAX_COMPLETION_TOKENS=true \
SUMMARIZER=stable_stage \
bash run_synthetic_perf_smoke.sh
```

## 搜索最大通过并发示例

```bash
cd /data/10.121.36.6/data/bohuai/release/cmcc_bench/performance_test

python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.3 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name "" \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
  --start-batch-size 1 \
  --max-batch-size 128 \
  --request-rate 0 \
  --min-request-count 30 \
  --parallel-strategy "PD分离 tp8 ep8" \
  --pd-ratio 1P1D \
  --tp-size 8 \
  --ep-size 8 \
  --pp-size 1 \
  --dp-size 1 \
  --etp-size 1 \
  --total-servers 2 \
  --prefill-servers 1 \
  --decoder-servers 1 \
  --total-cards 16 \
  --prefill-cards 8 \
  --decoder-cards 8 \
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene2_fast_search \
  --resource-ssh-target prefill=mccxadmin@10.121.31.84 \
  --resource-ssh-target decoder=mccxadmin@10.121.31.85
```

## 结果文件

- `summary.json`
  - 保存 rough/binary/confirm 的每次试点结果。
- `<scene>_summary_clean.csv`
  - 汇总输出，适合汇报。
