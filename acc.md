ais_bench --models vllm_api_general_chat --datasets aime2025_gen_0_shot_chat_prompt  --summarizer example

ais_bench --models vllm_api_general_chat --datasets aime2025_gen_0_shot_chat_prompt  --summarizer example --search 
查看路径

vi benchmark/ais_bench/benchmark/configs/models/vllm_api/vllm_api_general_chat.py
修改端口 ip


benchmark/ais_bench/benchmark/configs/datasets/aime2025
安装数据集

## 数据集部署
- 可以从opencompass提供的链接🔗 [http://opencompass.oss-cn-shanghai.aliyuncs.com/datasets/data/aime2025.zip](http://opencompass.oss-cn-shanghai.aliyuncs.com/datasets/data/aime2025.zip)下载数据集压缩包。
- 建议部署在`{工具根路径}/ais_bench/datasets`目录下（数据集任务中设置的默认路径），以linux上部署为例，具体执行步骤如下：
```bash
# linux服务器内，处于工具根路径下
cd ais_bench/datasets
wget http://opencompass.oss-cn-shanghai.aliyuncs.com/datasets/data/aime2025.zip
unzip aime2025.zip
rm aime2025.zip
```
- 在`{工具根路径}/ais_bench/datasets`目录下执行`tree aime2025/`查看目录结构，若目录结构如下所示，则说明数据集部署成功。
    ```
    aime2025/
    └── aime2025.jsonl
    ```
