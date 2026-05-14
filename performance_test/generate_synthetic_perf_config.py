#!/usr/bin/env python3

import argparse
import json
import pprint
from pathlib import Path


def str2bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    value = value.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def build_generation_kwargs(args: argparse.Namespace) -> dict:
    kwargs = {
        "temperature": args.temperature,
        "ignore_eos": args.ignore_eos,
        "enable_thinking": args.enable_thinking,
    }
    length_key = "max_completion_tokens" if args.use_max_completion_tokens else "max_tokens"
    kwargs[length_key] = args.output_len
    return kwargs


def build_dataset_config(args: argparse.Namespace) -> dict:
    if args.dataset_type == "string":
        return {
            "Type": "string",
            "RequestCount": args.request_count,
            "TrustRemoteCode": args.trust_remote_code,
            "StringConfig": {
                "Input": {
                    "Method": "uniform",
                    "Params": {"MinValue": args.input_len, "MaxValue": args.input_len},
                },
                "Output": {
                    "Method": "uniform",
                    "Params": {"MinValue": args.output_len, "MaxValue": args.output_len},
                },
            },
        }
    return {
        "Type": "tokenid",
        "RequestCount": args.request_count,
        "TrustRemoteCode": args.trust_remote_code,
        "TokenIdConfig": {
            "RequestSize": args.input_len,
            "PrefixLen": args.prefix_len,
        },
    }


def build_summarizer_block(args: argparse.Namespace) -> str:
    calculator_type = "StablePerfMetricCalculator" if args.summarizer == "stable_stage" else "DefaultPerfMetricCalculator"
    return f"""summarizer = dict(
    attr="performance",
    type=DefaultPerfSummarizer,
    calculator=dict(
        type={calculator_type},
        stats_list=["Average", "Min", "Max", "Median", "P75", "P90", "P95", "P99"],
    ),
)
"""


def render_config(args: argparse.Namespace) -> str:
    generation_kwargs = pprint.pformat(build_generation_kwargs(args), width=100, sort_dicts=False)
    dataset_config = pprint.pformat(build_dataset_config(args), width=100, sort_dicts=False)

    input_columns = '["question", "max_out_len"]' if args.dataset_type == "string" else '["question"]'

    return f"""from ais_bench.benchmark.models import VLLMCustomAPIChat
from ais_bench.benchmark.summarizers import DefaultPerfSummarizer
from ais_bench.benchmark.calculators import DefaultPerfMetricCalculator, StablePerfMetricCalculator
from ais_bench.benchmark.utils.postprocess.model_postprocessors import extract_non_reasoning_content
from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.datasets import SyntheticDataset

models = [
    dict(
        attr="service",
        type=VLLMCustomAPIChat,
        abbr="{args.model_abbr}",
        path=r"{args.model_path}",
        model={json.dumps(args.model_name)},
        stream=True,
        request_rate={args.request_rate},
        use_timestamp=False,
        retry={args.retry},
        api_key={json.dumps(args.api_key)},
        host_ip={json.dumps(args.host_ip)},
        host_port={args.host_port},
        url={json.dumps(args.url)},
        max_out_len={args.output_len},
        batch_size={args.batch_size},
        trust_remote_code={str(args.trust_remote_code)},
        generation_kwargs={generation_kwargs},
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    )
]

datasets = [
    dict(
        abbr="{args.dataset_abbr}",
        type=SyntheticDataset,
        config={dataset_config},
        reader_cfg=dict(
            input_columns={input_columns},
            output_column="answer",
        ),
        infer_cfg=dict(
            prompt_template=dict(type=PromptTemplate, template="{{question}}"),
            retriever=dict(type=ZeroRetriever),
            inferencer=dict(type=GenInferencer),
        ),
    )
]

{build_summarizer_block(args)}"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate AISBench synthetic perf config.")
    parser.add_argument("--output-config", required=True)
    parser.add_argument("--host-ip", required=True)
    parser.add_argument("--host-port", type=int, required=True)
    parser.add_argument("--model-name", default="")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--request-count", type=int, required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--request-rate", type=float, default=0.0)
    parser.add_argument("--input-len", type=int, required=True)
    parser.add_argument("--output-len", type=int, required=True)
    parser.add_argument("--dataset-type", choices=["string", "tokenid"], default="tokenid")
    parser.add_argument("--summarizer", choices=["stable_stage", "default_perf"], default="stable_stage")
    parser.add_argument("--enable-thinking", type=str2bool, default=False)
    parser.add_argument("--use-max-completion-tokens", type=str2bool, default=True)
    parser.add_argument("--ignore-eos", type=str2bool, default=True)
    parser.add_argument("--trust-remote-code", type=str2bool, default=False)
    parser.add_argument("--temperature", type=float, default=0.01)
    parser.add_argument("--retry", type=int, default=2)
    parser.add_argument("--prefix-len", type=int, default=0)
    parser.add_argument("--model-abbr", default="cmcc-minimax25")
    parser.add_argument("--dataset-abbr", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dataset_abbr:
        args.dataset_abbr = f"case_{args.input_len}_{args.output_len}_b{args.batch_size}_r{args.request_count}_{args.dataset_type}"
    output_path = Path(args.output_config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_config(args), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
