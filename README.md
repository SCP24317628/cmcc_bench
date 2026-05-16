# MiniMax M2.5 Launch And Test Commands

## 1. Service Startup

```bash
cd /data/cmcc/release/service
python3 generate_config.py --config 1p1d.json
```

```bash
cd /data/cmcc/release/service
bash setup_passwordless_ssh.sh
```

```bash
cd /data/cmcc/release/service
bash launch_servers.sh
```

## 2. Service Check

```bash
cd /data/cmcc/release/service
bash watch.sh
```

```bash
cd /data/cmcc/release/service
bash test.sh
```

## 3. AISBench Environment

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
```

## 4. AIME25 Accuracy Test

### 4.1 Search Config Path

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat --datasets aime2025_gen_0_shot_chat_prompt --summarizer example --search
```

### 4.2 Run AIME25 Accuracy Test

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat --datasets aime2025_gen_0_shot_chat_prompt --summarizer example
```

### 4.3 Dataset Note

- AIME25 dataset config: `aime2025_gen_0_shot_chat_prompt`
- If dataset file is missing, check `ais_bench/datasets/aime2025/aime2025.jsonl`

## 5. Perf Smoke Commands

### 5.1 40k / 200 / bs4

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat_perf_40000_200_bs4 --datasets synthetic_gen_tokenid_in40000 --summarizer stable_stage -m perf
```

### 5.2 4k / 1024 / bs16

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat_perf_4096_1024_bs16 --datasets synthetic_gen_tokenid_in4096 --summarizer stable_stage -m perf
```

### 5.3 7k / 2048 / bs8

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat_perf_7000_2048_bs8 --datasets synthetic_gen_tokenid_in7000 --summarizer stable_stage -m perf
```

### 5.4 16k / 2048 / bs4

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat_perf_16000_2048_bs4 --datasets synthetic_gen_tokenid_in16000 --summarizer stable_stage -m perf
```

### 5.5 512 / 8192 / bs16

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat_perf_512_8192_bs16 --datasets synthetic_gen_tokenid_in512 --summarizer stable_stage -m perf
```

### 5.6 128k / 1024 / bs1

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat_perf_128000_1024_bs1 --datasets synthetic_gen_tokenid_in128000 --summarizer stable_stage -m perf
```

## 6. Search Config Path

```bash
cd /data/cmcc/release/cmcc_bench/benchmark
source .venv/bin/activate
ais_bench --models vllm_api_general_chat_perf_40000_200_bs4 --datasets synthetic_gen_tokenid_in40000 --summarizer stable_stage --search
```

## 7. Resource Sampling

### 7.1 40k / 200 / bs4

```bash
cd /data/cmcc/release/cmcc_bench/performance_test
source ../benchmark/.venv/bin/activate
python3 sample_gpu_resources.py \
  --ssh-target prefill=mccxadmin@10.121.31.82 \
  --ssh-target decoder=mccxadmin@10.121.31.85 \
  --sample-count 6 \
  --interval-seconds 10 \
  --output /data/cmcc/release/cmcc_bench/outputs/resource_samples_smoke_40000_200_bs4.json
```

### 7.2 4k / 1024 / bs16

```bash
cd /data/cmcc/release/cmcc_bench/performance_test
source ../benchmark/.venv/bin/activate
python3 sample_gpu_resources.py \
  --ssh-target prefill=mccxadmin@10.121.31.82 \
  --ssh-target decoder=mccxadmin@10.121.31.85 \
  --sample-count 6 \
  --interval-seconds 10 \
  --output /data/cmcc/release/cmcc_bench/outputs/resource_samples_smoke_4096_1024_bs16.json
```

### 7.3 7k / 2048 / bs8

```bash
cd /data/cmcc/release/cmcc_bench/performance_test
source ../benchmark/.venv/bin/activate
python3 sample_gpu_resources.py \
  --ssh-target prefill=mccxadmin@10.121.31.82 \
  --ssh-target decoder=mccxadmin@10.121.31.85 \
  --sample-count 6 \
  --interval-seconds 10 \
  --output /data/cmcc/release/cmcc_bench/outputs/resource_samples_smoke_7000_2048_bs8.json
```

### 7.4 16k / 2048 / bs4

```bash
cd /data/cmcc/release/cmcc_bench/performance_test
source ../benchmark/.venv/bin/activate
python3 sample_gpu_resources.py \
  --ssh-target prefill=mccxadmin@10.121.31.82 \
  --ssh-target decoder=mccxadmin@10.121.31.85 \
  --sample-count 6 \
  --interval-seconds 10 \
  --output /data/cmcc/release/cmcc_bench/outputs/resource_samples_smoke_16000_2048_bs4.json
```

### 7.5 512 / 8192 / bs16

```bash
cd /data/cmcc/release/cmcc_bench/performance_test
source ../benchmark/.venv/bin/activate
python3 sample_gpu_resources.py \
  --ssh-target prefill=mccxadmin@10.121.31.82 \
  --ssh-target decoder=mccxadmin@10.121.31.85 \
  --sample-count 6 \
  --interval-seconds 10 \
  --output /data/cmcc/release/cmcc_bench/outputs/resource_samples_smoke_512_8192_bs16.json
```

### 7.6 128k / 1024 / bs1

```bash
cd /data/cmcc/release/cmcc_bench/performance_test
source ../benchmark/.venv/bin/activate
python3 sample_gpu_resources.py \
  --ssh-target prefill=mccxadmin@10.121.31.82 \
  --ssh-target decoder=mccxadmin@10.121.31.85 \
  --sample-count 6 \
  --interval-seconds 10 \
  --output /data/cmcc/release/cmcc_bench/outputs/resource_samples_smoke_128000_1024_bs1.json
```

## 8. Resource Summary

- prefill: GPU 0.0% / MEM 77.0%
- decoder: GPU 99.0% / MEM 85.125%

## 9. Notes

- Perf test must use `--summarizer stable_stage -m perf`.
- Do not use `--summarizer example` for perf, because it is an accuracy summarizer.
- Service entry URL:

```text
http://10.121.31.82:31001/v1/chat/completions
```
