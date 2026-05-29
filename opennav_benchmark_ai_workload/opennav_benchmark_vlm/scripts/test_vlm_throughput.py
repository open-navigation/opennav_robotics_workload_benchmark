#!/usr/bin/env python3

# Copyright 2026 Open Navigation LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
VLM throughput and latency benchmark.

Sends each (prompt, image) pair to the VLM server N times (default 10),
collecting per-request latency, token counts, and tokens/s. Prints a
summary table with mean, std, min, max for each query and overall.

Requires the VLM server to be running (e.g. llama.cpp / vLLM / Ollama)
at the configured base_url.

Usage:
    python3 test_vlm_throughput.py [--base-url URL] [--model MODEL] [--repeats N]
"""

import argparse
import base64
import json
import os
import platform
import statistics
import sys
import time

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'opennav_benchmark_vlm'),
)
from vlm_client import VLMClient

# ---------------------------------------------------------------------------
# Test queries: each entry is (prompt, image_path | None).
# image_path is relative to this script's directory; None = text-only query.
# ---------------------------------------------------------------------------
QUERIES = [
    (
        'Is there a person in this image? Reply yes, no, or unknown.',
        'images/warehouse_aisle.png',
    ),
    (
        'How many forklifts are visible? Reply with only an integer.',
        'images/warehouse_aisle.png',
    ),
    (
        'Describe the scene in one or two sentences, focusing on obstacles '
        'and hazards relevant to a mobile robot navigating this space.',
        'images/warehouse_aisle.png',
    ),
]

SYSTEM_PROMPT = (
    'You are the perception assistant for a mobile robot operating in an active '
    "warehouse, observing through the robot's onboard camera. Answer questions "
    "about the scene from the robot's point of view: what is present, what is "
    "happening, and what might affect the robot's ability to operate safely or "
    'make progress.\n\n'
    'Base every answer only on what is actually visible in the image. Do not '
    'speculate beyond what you can see. If you are not sure, say so rather than '
    'guessing. Accuracy matters more than completeness. '
    'Even if a simple "yes" or "no" answer is possible, always provide a brief explanation of your reasoning. '
    'If you are asked to describe the scene, provide a concise summary of the most important elements and '
    'their relationships, focusing on what is relevant to the robots operation and safety.'
)

# ---------------------------------------------------------------------------
# Defaults matching vlm_params.yaml
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = 'http://localhost:8080/v1'
DEFAULT_API_KEY = 'EMPTY'
DEFAULT_MODEL = 'gemma-4'
DEFAULT_TEMPERATURE = 1.0
DEFAULT_MAX_TOKENS = 256
DEFAULT_TIMEOUT = 360.0
DEFAULT_REPEATS = 10


def encode_image_file(path: str) -> str:
    """Read an image from disk and return a base64 data-URL (same format as image_utils.py)."""
    ext = os.path.splitext(path)[1].lower()
    mime = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
    }.get(ext, 'image/png')
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    return f'data:{mime};base64,{b64}'


def build_messages(prompt: str, image_url: str | None) -> list[dict]:
    """Build the chat-completions message list."""
    system_msg = {'role': 'system', 'content': SYSTEM_PROMPT}
    if image_url:
        user_content = [
            {'type': 'image_url', 'image_url': {'url': image_url}},
            {'type': 'text', 'text': prompt},
        ]
    else:
        user_content = [{'type': 'text', 'text': prompt}]
    user_msg = {'role': 'user', 'content': user_content}
    return [system_msg, user_msg]


def estimate_tokens(text: str) -> int:
    """Rough token count (~4 chars/token). Good enough for throughput estimates."""
    return max(1, len(text) // 4)


def run_benchmark(client: VLMClient, queries, repeats: int, timeout: float, script_dir: str):
    """Run all queries and return per-query and overall results."""
    all_results = []

    for q_idx, (prompt, image_rel) in enumerate(queries):
        image_url = None
        if image_rel:
            image_path = os.path.join(script_dir, image_rel)
            if not os.path.isfile(image_path):
                print(f'WARNING: image not found: {image_path} — skipping query {q_idx}')
                continue
            image_url = encode_image_file(image_path)

        messages = build_messages(prompt, image_url)

        latencies = []
        tokens_per_sec = []
        output_tokens = []

        print(f'\nQuery {q_idx}: "{prompt}"')
        for i in range(repeats):
            t0 = time.perf_counter()
            try:
                response = client.chat(messages, timeout=timeout)
            except Exception as e:
                print(f'  repeat {i + 1}/{repeats}: FAILED — {e}')
                continue
            elapsed = time.perf_counter() - t0

            n_tokens = estimate_tokens(response)
            tps = n_tokens / elapsed if elapsed > 0 else 0.0

            latencies.append(elapsed)
            tokens_per_sec.append(tps)
            output_tokens.append(n_tokens)

            print(f'  repeat {i + 1}/{repeats}: {elapsed:.3f}s, '
                  f'~{n_tokens} tokens, {tps:.1f} tok/s')

        if not latencies:
            print('  No successful runs.')
            continue

        result = {
            'query_index': q_idx,
            'prompt': prompt,
            'image': image_rel,
            'repeats_attempted': repeats,
            'repeats_succeeded': len(latencies),
            'latency_mean': statistics.mean(latencies),
            'latency_std': statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            'latency_min': min(latencies),
            'latency_max': max(latencies),
            'tokens_per_sec_mean': statistics.mean(tokens_per_sec),
            'tokens_per_sec_std': statistics.stdev(tokens_per_sec) if len(tokens_per_sec) > 1 else 0.0,
            'output_tokens_mean': statistics.mean(output_tokens),
            'latencies': latencies,
            'tokens_per_sec_all': tokens_per_sec,
        }
        all_results.append(result)

    return all_results


def print_summary(results, metadata):
    """Print a human-readable summary table and overall stats."""
    print('\n' + '=' * 80)
    print('VLM THROUGHPUT BENCHMARK RESULTS')
    print('=' * 80)

    print(f"\nPlatform:    {metadata['platform']}")
    print(f"CPU:         {metadata['cpu']}")
    print(f"Model:       {metadata['model']}")
    print(f"Base URL:    {metadata['base_url']}")
    print(f"Temperature: {metadata['temperature']}")
    print(f"Max tokens:  {metadata['max_tokens']}")
    print(f"Repeats:     {metadata['repeats']}")
    print(f"Timestamp:   {metadata['timestamp']}")

    if not results:
        print('\nNo successful results.')
        return

    print(f'\n{"Query":>5}  {"Latency (s)":>22}  {"Tokens/s":>22}  {"Avg Tokens":>10}  {"OK":>4}')
    print(f'{"":>5}  {"mean ± std (min–max)":>22}  {"mean ± std":>22}  {"":>10}  {"":>4}')
    print('-' * 80)

    all_latencies = []
    all_tps = []
    for r in results:
        all_latencies.extend(r['latencies'])
        all_tps.extend(r['tokens_per_sec_all'])
        lat = f"{r['latency_mean']:.3f}±{r['latency_std']:.3f} ({r['latency_min']:.3f}–{r['latency_max']:.3f})"
        tps = f"{r['tokens_per_sec_mean']:.1f}±{r['tokens_per_sec_std']:.1f}"
        print(f"{r['query_index']:>5}  {lat:>22}  {tps:>22}  {r['output_tokens_mean']:>10.1f}  {r['repeats_succeeded']:>4}")

    print('-' * 80)
    if all_latencies:
        overall_lat_mean = statistics.mean(all_latencies)
        overall_lat_std = statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0.0
        overall_tps_mean = statistics.mean(all_tps)
        overall_tps_std = statistics.stdev(all_tps) if len(all_tps) > 1 else 0.0
        total_queries = sum(r['repeats_succeeded'] for r in results)
        total_time = sum(all_latencies)
        throughput = total_queries / total_time if total_time > 0 else 0.0

        print(f'{"ALL":>5}  {overall_lat_mean:.3f}±{overall_lat_std:.3f} '
              f'({min(all_latencies):.3f}–{max(all_latencies):.3f})  '
              f'{overall_tps_mean:.1f}±{overall_tps_std:.1f}')
        print(f'\nTotal queries:    {total_queries}')
        print(f'Total wall time:  {total_time:.2f}s')
        print(f'Throughput:       {throughput:.2f} queries/s')


def get_cpu_info() -> str:
    """Best-effort CPU model string."""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
    except (FileNotFoundError, PermissionError):
        pass
    return platform.processor() or platform.machine()


def main():
    parser = argparse.ArgumentParser(description='VLM throughput and latency benchmark.')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help=f'VLM server URL (default: {DEFAULT_BASE_URL})')
    parser.add_argument('--api-key', default=DEFAULT_API_KEY,
                        help='API key (default: EMPTY)')
    parser.add_argument('--model', default=DEFAULT_MODEL,
                        help=f'Model name (default: {DEFAULT_MODEL})')
    parser.add_argument('--temperature', type=float, default=DEFAULT_TEMPERATURE,
                        help=f'Sampling temperature (default: {DEFAULT_TEMPERATURE})')
    parser.add_argument('--max-tokens', type=int, default=DEFAULT_MAX_TOKENS,
                        help=f'Max output tokens (default: {DEFAULT_MAX_TOKENS})')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT,
                        help=f'Request timeout in seconds (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--repeats', type=int, default=DEFAULT_REPEATS,
                        help=f'Repetitions per query (default: {DEFAULT_REPEATS})')
    parser.add_argument('--output-json', type=str, default=None,
                        help='Optional path to write JSON results for later analysis')
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    client = VLMClient(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    metadata = {
        'platform': platform.platform(),
        'cpu': get_cpu_info(),
        'python': platform.python_version(),
        'model': args.model,
        'base_url': args.base_url,
        'temperature': args.temperature,
        'max_tokens': args.max_tokens,
        'repeats': args.repeats,
        'timeout': args.timeout,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }

    print('VLM Throughput Benchmark')
    print(f'Server: {args.base_url}  Model: {args.model}  Repeats: {args.repeats}')

    results = run_benchmark(client, QUERIES, args.repeats, args.timeout, script_dir)
    print_summary(results, metadata)

    if args.output_json:
        output = {
            'metadata': metadata,
            'results': [
                {k: v for k, v in r.items() if k not in ('latencies', 'tokens_per_sec_all')}
                | {'latencies': r['latencies'], 'tokens_per_sec_all': r['tokens_per_sec_all']}
                for r in results
            ],
        }
        with open(args.output_json, 'w') as f:
            json.dump(output, f, indent=2)
        print(f'\nJSON results written to: {args.output_json}')


if __name__ == '__main__':
    main()
