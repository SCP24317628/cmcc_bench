# CMCC Bench 移交文档

## 1. 文档目标

这份文档用于把当前 `cmcc_bench` 的压测链路移交给另一台机器上的 AI 或工程同学，目标是：

1. 快速在新机器上部署一套与当前仓库一致的 AISBench 测试环境。
2. 用 OpenAI 兼容接口对 MiniMax M2.5 服务进行性能测试。
3. 在给定 `TTFT` / `TPOT` 约束下，搜索最大可通过并发，并产出标准化性能汇总表。

这份文档覆盖的是 **压测与结果整理链路**。它默认推理服务已经由外部脚本启动完成。也就是说：

- `cmcc_bench` 负责生成 AISBench 配置、发压、采样资源、汇总结果。
- `service/`、`service84(servicebak)`、`perf/` 这类目录负责远程起服务，不属于 `cmcc_bench` 自身。

如果另一台机器要“完整复现一套一样的服务 + 压测”，建议把本仓库的 `service/` 或匹配目标机器环境的 `servicebak/` 一并移交。

## 2. 目录说明

当前与性能测试最相关的目录如下：

```text
cmcc_bench/
├── benchmark/
│   ├── ais_bench/                              # AISBench 源码
│   ├── requirements.txt                        # AISBench 基础依赖
│   ├── requirements/api.txt                    # 服务化模型压测依赖
│   └── README.md                               # AISBench 官方说明
├── performance_test/
│   ├── RequirementDescription.txt              # CMCC 测试需求口径
│   ├── run_synthetic_perf_smoke.sh             # 单点 AISBench 压测入口
│   ├── generate_synthetic_perf_config.py       # 生成 SyntheticDataset 配置
│   ├── search_scene1_max_concurrency.py        # 在 TTFT/TPOT 约束下搜索最大并发
│   ├── sample_gpu_resources.py                 # 通过 SSH 采样 GPU 利用率/显存
│   └── CMCC_BENCH_Transfer_Guide.md            # 本文档
└── outputs/                                    # 历史输出目录
```

关键脚本职责：

- `run_synthetic_perf_smoke.sh`
  - 激活 `ais_bench` conda 环境。
  - 通过 `generate_synthetic_perf_config.py` 生成 AISBench 自定义配置。
  - 调用 `ais_bench <config> --mode perf --summarizer stable_stage --debug` 执行测试。
  - 校验输出目录中是否产出 `csv/json/html`。

- `generate_synthetic_perf_config.py`
  - 以 `SyntheticDataset` 自动生成 AISBench 配置文件。
  - 支持 `string` 和 `tokenid` 两种 SyntheticDataset。
  - 支持把 `enable_thinking`、`max_completion_tokens` 写入 `generation_kwargs`。

- `search_scene1_max_concurrency.py`
  - 负责自动搜索满足时延限制的最大 `batch_size`。
  - 搜索策略是：`rough` 倍增搜索 -> `binary` 二分收敛 -> `confirm` 确认。
  - 结果会落 `summary.json` 和 `<scene>_summary_clean.csv`。
  - 可以同时计算整机吞吐、单卡吞吐，并可选采样 GPU 利用率。

- `sample_gpu_resources.py`
  - 通过 SSH 调 `mthreads-gmi -q -d MEMORY,UTILIZATION --json`。
  - 适合 PD 分离场景下同时采样 prefill 机和 decoder 机。

## 3. 当前需求口径

来自 [RequirementDescription.txt](file:///data/bohuai/release/cmcc_bench/performance_test/RequirementDescription.txt) 的核心场景：

| 测试编号 | 场景 | IO | TTFT 要求 | TPOT 要求 | 目标 |
| --- | --- | --- | --- | --- | --- |
| 4.4.2 | agent/编程 | 40k / 200 | P90 TTFT <= 8s | 未明确 | 满足 TTFT 后测最大吞吐 |
| 4.4.3 | 对话 | 4k / 1k | P90 TTFT <= 2s | P90 TPOT <= 35ms | 满足时延后测最大吞吐 |
| 4.4.4 | 知识库 | 7k / 2k | P90 TTFT <= 4s | P90 TPOT <= 35ms | 满足时延后测最大吞吐 |
| 4.4.5 | 内容分析 | 16k / 2k | P90 TTFT <= 6s | P90 TPOT <= 35ms | 满足时延后测最大吞吐 |
| 4.4.6 | 内容生成 | 512 / 8k | P90 TTFT <= 2s | P90 TPOT <= 35ms | 满足时延后测最大吞吐 |
| 4.4.7 | 超长文本 | 128k / 1k | 未明确 | 未明确 | 测最大吞吐 |

统一要求：

- 使用 MiniMax M2.5 模型。
- 使用 AISBench。
- 按目标场景 IO 构造请求。
- 调整并发数和请求发送频率。
- 在满足 `P90 TTFT / P90 TPOT` 约束下记录：
  - 系统最大吞吐
  - 单服务器整机吞吐
  - 单卡吞吐
  - 平均/P90 TTFT
  - 平均/P90 TPOT
  - Output token throughput
  - 稳态 GPU 利用率和显存利用率

## 4. 新机器部署前提

### 4.1 必要前提

另一台机器必须满足：

1. 已有一个可访问的 OpenAI 兼容服务。
2. 服务至少支持：
   - `POST /v1/chat/completions`
   - 流式返回
3. 服务对应模型是 MiniMax M2.5。
4. 本地可访问 tokenizer/model path，用于 AISBench 计 token。
5. Python 版本为 `3.10/3.11/3.12`。

### 4.2 可选前提

如果要同时记录 GPU 利用率：

1. 测试机能 SSH 到 prefill/decoder 机器。
2. 远端有 `mthreads-gmi`。
3. SSH 最好免密。

## 5. 新机器最短部署步骤

### 5.1 复制仓库

建议直接把整个 `/data/bohuai/release` 打包复制到新机器，最少要有：

- `cmcc_bench/`
- `service/` 或适配目标环境的 `servicebak/`
- 模型目录或其挂载路径

### 5.2 安装 AISBench 环境

优先复用仓库内已有环境：

```bash
source /data/bohuai/release/cmcc_bench/miniconda3/bin/activate \
  /data/bohuai/release/cmcc_bench/miniconda3/envs/ais_bench
```

如果新机器没有这套 conda 环境，则新建：

```bash
cd /path/to/cmcc_bench/benchmark
conda create -n ais_bench python=3.10 -y
conda activate ais_bench
pip install -e ./ --use-pep517
pip install -r requirements/api.txt
pip install -r requirements/extra.txt
```

参考 AISBench 说明见 [README.md](file:///data/bohuai/release/cmcc_bench/benchmark/README.md#L77-L125)。

### 5.3 准备服务

注意：`cmcc_bench` 本身不负责启动推理服务。

你需要先把目标服务起好，然后确认：

```bash
curl http://<host>:<port>/v1/chat/completions
```

至少满足：

- IP/端口可达
- 模型已经加载
- 支持流式 chat/completions

### 5.4 确认 tokenizer 路径

`cmcc_bench` 有两个路径概念：

- `MODEL_NAME`
  - 发给服务端请求体里的模型名
  - 一般写服务端实际加载模型名，常见是 `/data/shared/models/MiniMax-M2.5-block-fp8`
- `MODEL_PATH`
  - AISBench 本地做 tokenizer 计数时使用的路径
  - 必须是本地可访问的 tokenizer/model 目录

如果新机器路径不同，这两个参数要一起改。

## 6. 推荐压测链路

推荐的执行顺序：

1. 先做 `smoke` 单点验证。
2. 再做 `search_scene1_max_concurrency.py` 自动搜索最大通过并发。
3. 最后查看 `summary.json` 和 `<scene>_summary_clean.csv`。

### 6.1 第一步：单点 smoke

脚本入口见 [run_synthetic_perf_smoke.sh](file:///data/bohuai/release/cmcc_bench/performance_test/run_synthetic_perf_smoke.sh)。

最小示例：

```bash
cd /data/bohuai/release/cmcc_bench/performance_test

HOST_IP=10.18.32.24 \
HOST_PORT=31001 \
MODEL_NAME=/data/shared/models/MiniMax-M2.5-block-fp8 \
MODEL_PATH=/data/bohuai/release/MiniMax-M2.5-block-fp8 \
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

成功后会产出：

- `performances/<model_abbr>/<dataset_abbr>.csv`
- `performances/<model_abbr>/<dataset_abbr>.json`
- `performances/<model_abbr>/<dataset_abbr>_plot.html`

### 6.2 第二步：搜索满足约束的最大并发

脚本入口见 [search_scene1_max_concurrency.py](file:///data/bohuai/release/cmcc_bench/performance_test/search_scene1_max_concurrency.py)。

这个脚本虽然名字叫 `scene1`，但实际上是通用搜索器，可以通过 `--scene-name` 跑任意场景。

输出：

- `summary.json`
- `<scene-name>_summary_clean.csv`

其中 `summary.json` 保存每个试点的完整结果，`*_summary_clean.csv` 用于直接汇报。

## 7. 标准命令模板

下面命令都假设：

- 服务地址为 `10.18.32.24:31001`
- tokenizer 路径为 `/data/bohuai/release/MiniMax-M2.5-block-fp8`
- 服务模型名为 `/data/shared/models/MiniMax-M2.5-block-fp8`
- 拓扑为 `1P1D, tp8 ep8, 16卡`

如果新机器不同，只改对应参数即可。

### 7.1 4.4.2 agent/编程场景 40k / 200

只约束 `TTFT`，`TPOT` 可给一个极大值：

```bash
cd /data/bohuai/release/cmcc_bench/performance_test

python3 search_scene1_max_concurrency.py \
  --scene-name scene1 \
  --ttft-limit-ms 8000 \
  --tpot-limit-ms 999999 \
  --input-len 40000 \
  --output-len 200 \
  --host-ip 10.18.32.24 \
  --host-port 31001 \
  --model-name /data/shared/models/MiniMax-M2.5-block-fp8 \
  --model-path /data/bohuai/release/MiniMax-M2.5-block-fp8 \
  --start-batch-size 1 \
  --max-batch-size 512 \
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
  --work-root /data/bohuai/release/cmcc_bench/outputs/scene1_fast_search \
  --resource-ssh-target prefill=mccxadmin@10.18.32.24 \
  --resource-ssh-target decoder=mccxadmin@10.18.31.34
```

当前已有一个参考结果：

- [summary.json](file:///data/bohuai/release/cmcc_bench/outputs/scene1_fast_search/summary.json)
- [scene1_summary_clean.csv](file:///data/bohuai/release/cmcc_bench/outputs/scene1_fast_search/scene1_summary_clean.csv)

其结论是：

- 最优通过并发 `batch_size = 6`
- `P90 TTFT = 6779.8 ms`
- `P90 TPOT = 125.8 ms`
- 输出吞吐 `42.9412 tok/s`

### 7.2 4.4.3 对话场景 4k / 1k

```bash
cd /data/bohuai/release/cmcc_bench/performance_test

python3 search_scene1_max_concurrency.py \
  --scene-name scene2 \
  --ttft-limit-ms 2000 \
  --tpot-limit-ms 35 \
  --input-len 4096 \
  --output-len 1000 \
  --host-ip 10.18.32.24 \
  --host-port 31001 \
  --model-name /data/shared/models/MiniMax-M2.5-block-fp8 \
  --model-path /data/bohuai/release/MiniMax-M2.5-block-fp8 \
  --start-batch-size 1 \
  --max-batch-size 512 \
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
  --work-root /data/bohuai/release/cmcc_bench/outputs/scene2_fast_search \
  --resource-ssh-target prefill=mccxadmin@10.18.32.24 \
  --resource-ssh-target decoder=mccxadmin@10.18.31.34
```

当前仓库里已有一份参考表：

- [scene2_summary_clean.csv](file:///data/bohuai/release/cmcc_bench/outputs/scene2_min4_stop/scene2_summary_clean.csv)

这份结果显示：

- `P90 TTFT = 461.4 ms`
- `P90 TPOT = 47.4 ms`

说明这组结果 **未满足 `TPOT <= 35 ms`**，因此只能作为失败示例，不应直接拿去汇报为最终通过值。

### 7.3 4.4.4 / 4.4.5 / 4.4.6 / 4.4.7

这些场景直接替换 `input-len / output-len / ttft-limit-ms / tpot-limit-ms / scene-name / work-root` 即可：

| 场景 | scene-name | input-len | output-len | ttft-limit-ms | tpot-limit-ms |
| --- | --- | ---: | ---: | ---: | ---: |
| 知识库 | scene3_kb | 7000 | 2000 | 4000 | 35 |
| 内容分析 | scene4_analysis | 16000 | 2000 | 6000 | 35 |
| 内容生成 | scene5_gen | 512 | 8000 | 2000 | 35 |
| 超长文本 | scene6_long | 128000 | 1000 | 999999 | 999999 |

## 8. 结果文件怎么看

### 8.1 AISBench 原始结果

单次运行的原始结果主要看：

- `performances/<model>/<dataset>.csv`
- `performances/<model>/<dataset>.json`

示例：

- [case_65536_2048_b16_default.csv](file:///data/bohuai/release/cmcc_bench/outputs/case_65536_2048_b16_r64_default/20260512_194208/performances/cmcc-minimax25-default-b16/case_65536_2048_b16_default.csv)
- [case_65536_2048_b16_default.json](file:///data/bohuai/release/cmcc_bench/outputs/case_65536_2048_b16_r64_default/20260512_194208/performances/cmcc-minimax25-default-b16/case_65536_2048_b16_default.json)

重点字段：

- `TTFT`
- `TPOT`
- `OutputTokenThroughput`
- `Request Throughput`
- `Concurrency`

### 8.2 搜索结果

自动搜索后的最终报告主要看：

- `summary.json`
- `<scene-name>_summary_clean.csv`

其中：

- `summary.json`
  - 适合追溯每个试点是否通过。
  - 能看到 rough/binary/confirm 每一次的详情。
- `*_summary_clean.csv`
  - 适合汇报。
  - 已包含整机吞吐、单卡吞吐、TTFT/TPOT、拓扑信息、模型名、时间戳。

## 9. 为什么推荐 `tokenid + enable_thinking=false + max_completion_tokens`

这是当前链路最重要的经验之一。

### 9.1 `tokenid` 比 `string` 更适合正式性能测试

`run_synthetic_perf_smoke.sh` 默认 `DATASET_TYPE=string`，适合 smoke。

但正式场景为了严格控制输入长度，建议使用：

```bash
DATASET_TYPE=tokenid
```

原因：

- `string` 会先构造文本，再由服务端重新 tokenize，输入长度可能漂移。
- `tokenid` 更接近“按 token 数精确造请求”。

搜索脚本内部已经固定：

- `DATASET_TYPE=tokenid`

见 [search_scene1_max_concurrency.py](file:///data/bohuai/release/cmcc_bench/performance_test/search_scene1_max_concurrency.py#L240-L244)。

### 9.2 必须显式关 thinking

对当前 MiniMax M2.5 chat/completions 服务，如果只给 `max_tokens`，预算可能被 reasoning/thinking 吃掉，导致输出长度不稳定。

当前链路已固定：

- `ENABLE_THINKING=false`
- `USE_MAX_COMPLETION_TOKENS=true`

对应：

- [run_synthetic_perf_smoke.sh](file:///data/bohuai/release/cmcc_bench/performance_test/run_synthetic_perf_smoke.sh#L34-L37)
- [generate_synthetic_perf_config.py](file:///data/bohuai/release/cmcc_bench/performance_test/generate_synthetic_perf_config.py#L59-L64)
- [generate_synthetic_perf_config.py](file:///data/bohuai/release/cmcc_bench/performance_test/generate_synthetic_perf_config.py#L149-L155)

这三项组合的意义是：

1. `enable_thinking=false`
2. `max_completion_tokens=目标输出长度`
3. `ignore_eos=true`

这样更容易让输出 token 数对齐目标长度，避免因为 reasoning 导致 TPOT/吞吐结果失真。

## 10. 为什么必须用 `stable_stage`

对服务化稳态性能测试，必须看 `stable_stage` 口径。

当前 smoke 脚本默认：

```bash
SUMMARIZER=stable_stage
```

对应 [run_synthetic_perf_smoke.sh](file:///data/bohuai/release/cmcc_bench/performance_test/run_synthetic_perf_smoke.sh#L37-L37)。

如果不用 `stable_stage`，可能得到的是 total 口径而不是稳态口径，不适合拿来做最终对外汇报。

## 11. 另一台机器 AI 最容易踩的坑

### 11.1 把 `cmcc_bench` 当成服务启动器

不是。

- `cmcc_bench` 只负责压测与汇总。
- 服务必须先由 `service/`、`servicebak/` 或其他部署脚本拉起。

### 11.2 `MODEL_NAME` 和 `MODEL_PATH` 混淆

- `MODEL_NAME` 是请求发给服务端的模型名。
- `MODEL_PATH` 是本地 tokenizer 路径。

两者路径可以相同，也可以不同。

### 11.3 只传 `max_tokens`，没关 thinking

这样最容易出现：

- 输出长度漂移
- TPOT 看起来异常
- 结果跨机不可比

### 11.4 用 `string` 方式跑正式吞吐

正式场景建议用 `tokenid`，避免 IO 漂移。

### 11.5 忽略 `stable_stage`

如果目的是“满足 TTFT/TPOT 约束后给出稳态最大吞吐”，就不能只看 total。

### 11.6 资源采样没配 SSH

如果没传 `--resource-ssh-target`，结果仍然能跑，但不会有 GPU 利用率样本。

### 11.7 新机器服务路径不同

如果服务端模型路径不是 `/data/shared/models/...`，至少要同步核对：

- `MODEL_NAME`
- `MODEL_PATH`
- 服务端实际已加载的模型名

## 12. 建议的移交流程

建议把以下内容一起移交给另一台机器的 AI：

1. 本文档。
2. `cmcc_bench/` 整个目录。
3. 匹配该机器环境的服务启动目录：
   - `service/`
   - 或 `service84.tar.gz` 解出的 `servicebak/`
4. 一份明确的服务地址和模型路径说明：
   - `host_ip`
   - `host_port`
   - `model_name`
   - `model_path`
   - `prefill/decode` 机器 SSH 地址

## 13. 推荐交给另一台机器 AI 的任务描述

可以直接把下面这段话发给对方：

```text
请基于 /path/to/release/cmcc_bench/performance_test/CMCC_BENCH_Transfer_Guide.md 部署并复现 AISBench 性能测试链路。

目标：
1. 先确认 OpenAI 兼容服务已启动并可访问。
2. 用 run_synthetic_perf_smoke.sh 做一个 tokenid 模式 smoke。
3. 再用 search_scene1_max_concurrency.py 按指定 IO 和 TTFT/TPOT 限制搜索最大可通过并发。
4. 输出 summary.json 和 <scene>_summary_clean.csv。

注意：
- 正式性能测试必须使用 SyntheticDataset(tokenid)。
- generation_kwargs 必须带 enable_thinking=false。
- 必须带 max_completion_tokens=目标输出长度。
- summarizer 必须使用 stable_stage。
- 如果有 PD 分离架构，请同时配置 resource_ssh_target 采样 GPU 利用率。
```

## 14. 当前仓库可直接参考的结果

- agent/编程场景 40k/200 搜索结果：
  - [summary.json](file:///data/bohuai/release/cmcc_bench/outputs/scene1_fast_search/summary.json)
  - [scene1_summary_clean.csv](file:///data/bohuai/release/cmcc_bench/outputs/scene1_fast_search/scene1_summary_clean.csv)

- 对话场景 4k/1k 失败示例：
  - [summary.json](file:///data/bohuai/release/cmcc_bench/outputs/scene2_min4_stop/summary.json)
  - [scene2_summary_clean.csv](file:///data/bohuai/release/cmcc_bench/outputs/scene2_min4_stop/scene2_summary_clean.csv)

- 单点 64k/2k 结果示例：
  - [case_65536_2048_b16_default.csv](file:///data/bohuai/release/cmcc_bench/outputs/case_65536_2048_b16_r64_default/20260512_194208/performances/cmcc-minimax25-default-b16/case_65536_2048_b16_default.csv)
  - [case_65536_2048_b16_default.json](file:///data/bohuai/release/cmcc_bench/outputs/case_65536_2048_b16_r64_default/20260512_194208/performances/cmcc-minimax25-default-b16/case_65536_2048_b16_default.json)

## 15. 一句话总结

在另一台机器上快速复现同样的 AISBench 性能链路，核心不是“重新写脚本”，而是保证以下四件事完全一致：

1. 同样的服务接口和模型名。
2. 同样的 tokenizer 路径。
3. 同样的 `SyntheticDataset(tokenid) + enable_thinking=false + max_completion_tokens + stable_stage` 测试口径。
4. 同样的 TTFT/TPOT 约束搜索流程和结果汇总格式。
