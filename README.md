# CMCC Bench for MiniMax M2.5

这个仓库用于复现 `RequirementDescription.txt` 和 `CMCC_BENCH_Transfer_Guide.md` 约定的 AISBench 性能测试流程，目标是让别人直接拉取本仓库后，只补一份官方 AISBench 代码，就能完成：

- smoke 单点验证
- `4.4.2 ~ 4.4.7` 场景正式测试
- 最大通过并发搜索
- GPU / 显存利用率采样

## 仓库定位

这个仓库只保存和 CMCC 场景相关的内容：

- 场景需求说明
- AISBench 适配脚本
- smoke / 正式测试入口
- 复现文档

这个仓库**不直接提交**下面两类内容：

- `benchmark/`
  - 官方 AISBench 上游代码，使用时单独 clone 到本目录下
- `outputs/`
  - 历史跑数结果、HTML 图表、数据库、中间 JSONL

这样做的目的是让仓库更轻，避免把第三方上游和本地测试产物一起塞进 GitHub。

## 目录结构

```text
cmcc_bench/
├── README.md
├── SETUP_README.md
├── RequirementDescription.txt
├── CMCC_BENCH_Transfer_Guide.md
└── performance_test/
    ├── README.md
    ├── scene_requirements.json
    ├── generate_synthetic_perf_config.py
    ├── run_synthetic_perf_smoke.sh
    ├── search_scene1_max_concurrency.py
    └── sample_gpu_resources.py
```

## 快速开始

### 1. 克隆本仓库

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd cmcc_bench
```

### 2. 拉取官方 AISBench 到 `benchmark/`

脚本默认按 `cmcc_bench/benchmark` 这个相对路径寻找 AISBench，所以请直接在仓库根目录执行：

```bash
git clone https://github.com/AISBench/benchmark.git benchmark
cd benchmark
```

### 3. 创建虚拟环境并安装 AISBench

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e . --use-pep517
```

如果下载慢，可以先切换清华源：

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
```

如果后续缺少 API 依赖，再补：

```bash
pip install -r requirements/api.txt
```

### 4. 回到 `performance_test` 跑 smoke

```bash
cd ../performance_test
```

示例：

```bash
HOST_IP=<HOST_IP> \
HOST_PORT=<HOST_PORT> \
MODEL_NAME='<MODEL_NAME>' \
MODEL_PATH=<MODEL_PATH> \
REQUEST_COUNT=4 \
BATCH_SIZE=1 \
REQUEST_RATE=0 \
INPUT_LEN=4096 \
OUTPUT_LEN=1000 \
DATASET_TYPE=tokenid \
ENABLE_THINKING=false \
USE_MAX_COMPLETION_TOKENS=true \
IGNORE_EOS=true \
SUMMARIZER=stable_stage \
bash run_synthetic_perf_smoke.sh
```

## 核心文件

- `SETUP_README.md`
  - 最完整的安装、冒烟、正式场景、迁移和利用率采集说明
- `performance_test/run_synthetic_perf_smoke.sh`
  - 固定单点 smoke / 手动验证入口
- `performance_test/search_scene1_max_concurrency.py`
  - 按 TTFT / TPOT 约束搜索最大通过并发
- `performance_test/sample_gpu_resources.py`
  - 通过 SSH 采集 GPU / 显存利用率
- `performance_test/scene_requirements.json`
  - `4.4.2 ~ 4.4.7` 的场景参数基表

## 正式测试方法

这套方法本质上是在做：

- 固定模型
- 固定输入输出长度
- 固定服务拓扑
- 固定测试口径
- 通过 `rough -> binary -> confirm`
- 找到满足 `P90 TTFT / P90 TPOT` 约束的最大通过并发
- 再把该并发点的吞吐、时延和单卡指标作为最终答案

正式场景入口示例：

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.3 \
  --host-ip <HOST_IP> \
  --host-port <HOST_PORT> \
  --model-name '<MODEL_NAME>' \
  --model-path <MODEL_PATH> \
  --start-batch-size 1 \
  --max-batch-size 16 \
  --request-rate 0 \
  --min-request-count 30 \
  --parallel-strategy 'PD分离 tp8 ep8' \
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
  --work-root <WORK_ROOT> \
  --live-output
```

## 项目约定

- `benchmark/` 是外部依赖目录，拉取后本地使用，但不提交到 GitHub
- `outputs/` 是本地测试产物目录，默认全部忽略
- 本仓库关注“测试方法、脚本、文档”，不保存模型权重、服务二进制或历史跑数

## 推荐阅读顺序

1. `README.md`
2. `SETUP_README.md`
3. `performance_test/README.md`
4. `RequirementDescription.txt`
5. `CMCC_BENCH_Transfer_Guide.md`
