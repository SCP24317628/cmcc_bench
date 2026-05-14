# CMCC Bench Setup README

这份文档记录当前 `cmcc_bench` 目录下，基于官方 AISBench 仓库完成最小安装和冒烟测试的步骤。

适用场景：

- 已经有一个可访问的 OpenAI 兼容服务
- 只想先把 AISBench 环境装起来
- 先验证 `cmcc_bench/performance_test` 这套插件层脚本能跑通

## 1. 获取 AISBench

先拉官方仓库：

```bash
git clone https://github.com/AISBench/benchmark.git
cd benchmark
```

## 2. 创建虚拟环境

不要把虚拟环境建成 `ais_bench` 目录名，建议使用 `.venv`：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

如果下载太慢，可以先切换清华源：

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
```

## 3. 安装 AISBench

在 `benchmark` 仓库根目录执行：

```bash
pip install --upgrade pip setuptools wheel
pip install -e . --use-pep517
```

如果后续缺少 API 测试相关依赖，再补：

```bash
pip install -r requirements/api.txt
```

## 4. 进入 cmcc_bench 插件目录

安装完成后，进入当前项目的性能测试目录：

```bash
cd cmcc_bench/performance_test
```

这里的脚本是对 AISBench 的一层封装，主要用途是：

- 生成符合当前项目口径的 synthetic config
- 调用 AISBench 跑单点测试
- 后续支持按场景搜索最大通过并发

## 5. 运行冒烟测试

在已经激活的 `.venv` 环境中，执行下面这条命令：

```bash
HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME='' \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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

## 6. 参数说明

- `HOST_IP`
  - 服务 IP
- `HOST_PORT`
  - 服务端口
- `MODEL_NAME`
  - 发给服务端请求体里的模型名
  - 如果服务端不强校验，可以留空字符串
- `MODEL_PATH`
  - 本地 tokenizer / model 路径
  - `tokenid` 模式下必须可访问
- `REQUEST_COUNT`
  - 本次测试请求数
- `BATCH_SIZE`
  - 本次测试目标并发
- `REQUEST_RATE`
  - 请求速率，`0` 表示尽快发出
- `INPUT_LEN`
  - 输入 token 长度
- `OUTPUT_LEN`
  - 输出 token 长度
- `DATASET_TYPE`
  - 当前正式性能建议使用 `tokenid`
- `ENABLE_THINKING=false`
  - 关闭 thinking，避免额外消耗输出预算
- `USE_MAX_COMPLETION_TOKENS=true`
  - 用 `max_completion_tokens` 控制输出长度
- `IGNORE_EOS=true`
  - 减少 EOS 提前截断影响
- `SUMMARIZER=stable_stage`
  - 正式汇总建议使用这个口径

## 6.1 移植到其他机器时，哪些参数会变

如果你把这套测试移植到另一台机器，通常只需要改“机器相关参数”，场景参数一般不变。

### 机器相关参数

下面这些参数通常和部署机器、服务地址、模型挂载路径有关，换机器时最常需要改：

- `HOST_IP`
  - 目标服务 IP
- `HOST_PORT`
  - 目标服务端口
- `MODEL_NAME`
  - 服务端实际识别的模型名
  - 有些服务允许空字符串，有些服务要求写真实模型名
- `MODEL_PATH`
  - 新机器上本地可访问的 tokenizer / model 路径
  - 如果新机器挂载路径变了，这里必须一起改

### 场景固定参数

下面这些参数通常由测试场景本身决定，换机器时一般不改：

- `INPUT_LEN`
  - 输入 token 长度
- `OUTPUT_LEN`
  - 输出 token 长度
- `DATASET_TYPE=tokenid`
- `ENABLE_THINKING=false`
- `USE_MAX_COMPLETION_TOKENS=true`
- `IGNORE_EOS=true`
- `SUMMARIZER=stable_stage`

### 与测试策略相关的参数

这些参数不一定固定，但通常和“你想怎么测”有关，而不是和机器绑定：

- `REQUEST_COUNT`
  - 冒烟时一般设小一点，比如 `4`
  - 正式搜索时脚本会自动按阶段放大
- `BATCH_SIZE`
  - 冒烟时常设 `1`
  - 正式搜索时由搜索脚本自动调节
- `REQUEST_RATE`
  - 目前这套方法里通常用 `0`
  - 表示尽快送出请求，更接近压满当前并发

## 6.2 冒烟测试参数模板

移植到新机器时，你可以先把下面 4 个值替换掉，再直接跑冒烟：

- `<HOST_IP>`
- `<HOST_PORT>`
- `<MODEL_NAME>`
- `<MODEL_PATH>`

模板如下：

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

说明：

- 上面这条模板默认是 `4.4.3 / 4k / 1k` 的冒烟口径
- 如果你只是想验证环境和服务通不通，这一条最适合先跑
- 如果要切到别的场景，只需要改 `INPUT_LEN` 和 `OUTPUT_LEN`

## 6.3 正式测试参数模板

正式测试建议使用搜索脚本。
移植到新机器时，一般只要替换下面这些值：

- `<HOST_IP>`
- `<HOST_PORT>`
- `<MODEL_NAME>`
- `<MODEL_PATH>`
- `<WORK_ROOT>`

模板如下：

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name <SCENE_NAME> \
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

说明：

- `<SCENE_NAME>` 可以写：
  - `4.4.2`
  - `4.4.3`
  - `4.4.4`
  - `4.4.5`
  - `4.4.6`
  - `4.4.7`
- 这些场景对应的 `INPUT_LEN / OUTPUT_LEN / TTFT / TPOT` 会从
  - `performance_test/scene_requirements.json`
  自动读取
- 所以正式测试时一般不需要手工再写 `INPUT_LEN` 和 `OUTPUT_LEN`

## 7. 结果位置

命令成功后，结果默认会落到：

```bash
/data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/
```

每次运行通常会生成：

- `config.py`
- `performances/.../*.csv`
- `performances/.../*.json`
- `performances/.../*_plot.html`

## 8. 常见问题

### 8.1 下载依赖太慢

建议先设置清华源：

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
```

### 8.2 已经安装了 AISBench，但还是导入失败

先确认当前环境真的已经激活：

```bash
which python
python -c "import ais_bench.benchmark.cli.main; print('ok')"
```

如果这里失败，说明是 AISBench 环境本身没有安装好，不是 `performance_test` 脚本的问题。


## 9. 后续正式测试入口

冒烟通过后，可以继续使用：

- `run_synthetic_perf_smoke.sh`
  - 跑固定单点
- `search_scene1_max_concurrency.py`
  - 按场景自动搜索最大通过并发

如果只是最小复现，先保证本 README 中的冒烟命令可以跑通即可。

## 10. 后续场景如何手动运行

后续场景有两种常见跑法：

- 固定一个点做手动验证
- 用搜索脚本自动找最大通过并发

建议顺序：

1. 先用 `run_synthetic_perf_smoke.sh` 跑一个固定点，确认服务和 token 长度正常
2. 再用 `search_scene1_max_concurrency.py` 跑正式场景搜索

### 10.1 固定点手动验证

下面这些命令都默认你已经：

- 激活了 `.venv`
- 进入了 `cmcc_bench/performance_test`

```bash
cd /data/10.121.36.6/data/bohuai/release/cmcc_bench/performance_test
```

#### 4.4.2 agent/编程场景，40k / 200

```bash
HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME='' \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
REQUEST_COUNT=4 \
BATCH_SIZE=1 \
REQUEST_RATE=0 \
INPUT_LEN=40000 \
OUTPUT_LEN=200 \
DATASET_TYPE=tokenid \
ENABLE_THINKING=false \
USE_MAX_COMPLETION_TOKENS=true \
IGNORE_EOS=true \
SUMMARIZER=stable_stage \
bash run_synthetic_perf_smoke.sh
```

#### 4.4.3 对话场景，4k / 1k

```bash
HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME='' \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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

#### 4.4.4 知识库场景，7k / 2k

```bash
HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME='' \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
REQUEST_COUNT=4 \
BATCH_SIZE=1 \
REQUEST_RATE=0 \
INPUT_LEN=7000 \
OUTPUT_LEN=2000 \
DATASET_TYPE=tokenid \
ENABLE_THINKING=false \
USE_MAX_COMPLETION_TOKENS=true \
IGNORE_EOS=true \
SUMMARIZER=stable_stage \
bash run_synthetic_perf_smoke.sh
```

#### 4.4.5 内容分析场景，16k / 2k

```bash
HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME='' \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
REQUEST_COUNT=4 \
BATCH_SIZE=1 \
REQUEST_RATE=0 \
INPUT_LEN=16000 \
OUTPUT_LEN=2000 \
DATASET_TYPE=tokenid \
ENABLE_THINKING=false \
USE_MAX_COMPLETION_TOKENS=true \
IGNORE_EOS=true \
SUMMARIZER=stable_stage \
bash run_synthetic_perf_smoke.sh
```

#### 4.4.6 内容生成场景，512 / 8k

```bash
HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME='' \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
REQUEST_COUNT=4 \
BATCH_SIZE=1 \
REQUEST_RATE=0 \
INPUT_LEN=512 \
OUTPUT_LEN=8000 \
DATASET_TYPE=tokenid \
ENABLE_THINKING=false \
USE_MAX_COMPLETION_TOKENS=true \
IGNORE_EOS=true \
SUMMARIZER=stable_stage \
bash run_synthetic_perf_smoke.sh
```

#### 4.4.7 超长文本场景，128k / 1k

```bash
HOST_IP=10.121.31.84 \
HOST_PORT=31001 \
MODEL_NAME='' \
MODEL_PATH=/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
REQUEST_COUNT=4 \
BATCH_SIZE=1 \
REQUEST_RATE=0 \
INPUT_LEN=128000 \
OUTPUT_LEN=1000 \
DATASET_TYPE=tokenid \
ENABLE_THINKING=false \
USE_MAX_COMPLETION_TOKENS=true \
IGNORE_EOS=true \
SUMMARIZER=stable_stage \
bash run_synthetic_perf_smoke.sh
```

### 10.2 正式场景搜索命令

如果不是只测单点，而是要按正式口径搜索最大通过并发，使用：

```bash
python3 search_scene1_max_concurrency.py ...
```

这个脚本虽然名字叫 `scene1`，但实际上可以跑所有场景。

下面给出每个场景的直接可用命令模板。

公共参数保持一致：

- 服务 IP：`10.121.31.84`
- 服务端口：`31001`
- 模型路径：`/data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8`
- 并行策略：`PD分离 tp8 ep8`
- PD 配比：`1P1D`
- 服务器数：`2`
- 总卡数：`16`

#### 4.4.2 agent/编程场景，40k / 200

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.2 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene1_agent_manual \
  --live-output
```

#### 4.4.3 对话场景，4k / 1k

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.3 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene2_chat_manual \
  --live-output
```

#### 4.4.4 知识库场景，7k / 2k

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.4 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene3_kb_manual \
  --live-output
```

#### 4.4.5 内容分析场景，16k / 2k

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.5 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene4_analysis_manual \
  --live-output
```

#### 4.4.6 内容生成场景，512 / 8k

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.6 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene5_generation_manual \
  --live-output
```

#### 4.4.7 超长文本场景，128k / 1k

这个场景没有明确 TTFT / TPOT 约束，更关注最大吞吐。
可以先按下面方式跑一轮并发搜索；如果 `16` 还没有到瓶颈，再把 `--max-batch-size` 继续提高到 `32`。

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.7 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene6_long_context_manual \
  --live-output
```

### 10.3 搜索结果怎么看

每个场景搜索完成后，主要看两类文件：

- `summary.json`
  - 保存 rough / binary / confirm 全过程
- `<scene>_summary_clean.csv`
  - 汇总后的最终清洗表

例如：

- `scene2_chat_summary_clean.csv`
- `scene4_analysis_summary_clean.csv`
- `scene6_long_context_summary_clean.csv`

如果只是想汇报最终结果，优先看 `*_summary_clean.csv` 即可。

## 11. 如何采集稳定运行后的内存利用率和 GPU 利用率

`RequirementDescription.txt` 里除了时延和吞吐，还要求：

- 稳定运行后的内存利用率
- 稳定运行后的 GPU 利用率

这部分不是从 AISBench 自己的时延 CSV 里推出来的，而是通过额外脚本在压测进行时同步采样。

当前项目里对应的采样脚本是：

- `performance_test/sample_gpu_resources.py`

正式场景搜索脚本里也已经接入了这个能力：

- `search_scene1_max_concurrency.py`

### 11.1 采样前提

要采集这两项指标，需要满足下面几个条件：

1. 压测机可以 SSH 到服务机器
2. 服务机器上安装了 `mthreads-gmi`
3. 远端执行下面命令可以返回 JSON：

```bash
mthreads-gmi -q -d MEMORY,UTILIZATION --json
```

如果是 PD 分离部署，通常要同时采两个目标：

- prefill 机器
- decoder 机器

### 11.2 直接手动采样

如果你只是想单独验证资源采样脚本，可以直接运行：

```bash
cd /data/10.121.36.6/data/bohuai/release/cmcc_bench/performance_test

python3 sample_gpu_resources.py \
  --ssh-target prefill=mccxadmin@10.121.31.84 \
  --ssh-target decoder=mccxadmin@10.121.31.85 \
  --sample-count 6 \
  --interval-seconds 10 \
  --output /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/resource_samples_manual.json
```

说明：

- `--ssh-target`
  - 格式是 `role=user@host`
- `--sample-count`
  - 采样次数
- `--interval-seconds`
  - 每次采样间隔秒数
- `--output`
  - 采样结果 JSON 输出路径

输出结果里会包含：

- `gpu_util_avg`
- `gpu_util_max`
- `memory_util_avg`
- `memory_util_max`

### 11.3 在正式搜索时自动采样

更推荐的方式是在正式场景搜索时，直接把资源采样参数一起带上。
这样脚本会在最终通过点运行结束后自动采样，并把结果写进清洗表。

在原来的搜索命令基础上，额外加这几个参数：

```bash
--resource-ssh-target prefill=mccxadmin@10.121.31.84 \
--resource-ssh-target decoder=mccxadmin@10.121.31.85 \
--resource-sample-count 6 \
--resource-interval-seconds 10
```

完整示例，以 `4.4.3 / 4k / 1k` 为例：

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.3 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
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
  --resource-ssh-target prefill=mccxadmin@10.121.31.84 \
  --resource-ssh-target decoder=mccxadmin@10.121.31.85 \
  --resource-sample-count 6 \
  --resource-interval-seconds 10 \
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene2_chat_with_resource \
  --live-output
```

### 11.4 如何只对最终通过点补采资源

如果场景已经测过，不想从 `b1` 重新开始，可以直接把 `start-batch-size` 和 `max-batch-size` 都设成最终通过点。

例如 `4.4.3` 最终通过点是 `16`，那么可以这样补采：

```bash
python3 search_scene1_max_concurrency.py \
  --scene-name 4.4.3 \
  --host-ip 10.121.31.84 \
  --host-port 31001 \
  --model-name '' \
  --model-path /data/10.121.36.6/data/models/silicon/MiniMax-M2.5-block-fp8 \
  --start-batch-size 16 \
  --max-batch-size 16 \
  --request-rate 0 \
  --min-request-count 80 \
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
  --resource-ssh-target prefill=mccxadmin@10.121.31.84 \
  --resource-ssh-target decoder=mccxadmin@10.121.31.85 \
  --resource-sample-count 6 \
  --resource-interval-seconds 10 \
  --work-root /data/10.121.36.6/data/bohuai/release/cmcc_bench/outputs/scene2_chat_b16_with_resource \
  --live-output
```

这种方式适合：

- 前面的时延和吞吐已经测完
- 只差资源利用率还没采

### 11.5 结果会写到哪里

如果资源采样成功，结果会出现在两个地方：

1. `resource_samples.json`
   - 保存原始采样结果
2. `*_summary_clean.csv`
   - 会写入：
     - `GPU Util Avg`
     - `Memory Util Avg`

### 11.6 常见注意事项

- 如果 `GPU Util Avg` 和 `Memory Util Avg` 为空：
  - 一般是没有传 `--resource-ssh-target`
  - 或者远端 `mthreads-gmi` 执行失败
- 如果想让“稳定运行后的利用率”更稳定：
  - 可以适当增大：
    - `--resource-sample-count`
    - `--resource-interval-seconds`
- 如果是单机非 PD 部署：
  - 只传一个 `--resource-ssh-target` 也可以
