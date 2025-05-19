from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from openai import OpenAI  
from tqdm import tqdm


CONCURRENT_REQUESTS: int = 10  
TARGET_FIELD_NAME: str = "Geminiflash_4in1_choice"  
CORRECT_LABEL_FIELD: str = "ground-truth"          
POSSIBLE_OPTIONS: Sequence[str] = ("a", "b", "c", "d")

def _call_llm_api(prompt: str, model: str, client: OpenAI) -> str:
    """Send *prompt* to *model* via *client* and return the raw content text."""
    try:
        rsp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return rsp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001  (broad cast on purpose)
        return f"LLM API 调用异常: {exc}"


def _count_lines(path: Path) -> int:
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def _build_prompt(question: str, options: Dict[str, str]) -> str:
    """Compose the Chinese instruction plus question and four options."""
    return (
        "你是一位数学领域的顶尖专家，下面是一道证明/推导类选择题，请从 a/b/c/d 中选出唯一正确的一项，"
        "回答格式仅包含“答案：a”这样的内容。\n\n"
        f"问题：\n{question}\n\n"
        f"a.\n{options['a']}\n\n"
        f"b.\n{options['b']}\n\n"
        f"c.\n{options['c']}\n\n"
        f"d.\n{options['d']}\n"
    )


def _parse_option(text: str | None) -> str | None:
    """Extract the first occurrence of a/b/c/d (case‑insensitive) from *text*."""
    if not text:
        return None
    m = re.search(r"([a-d])", text.lower())
    return m.group(1) if m else None

def _process_batch(
    batch: List[Tuple[dict[str, Any], str]],
    model: str,
    client: OpenAI,
) -> List[Tuple[dict[str, Any], str]]:
    """Send *batch* of prompts; return list of (record, llm_output)."""
    prompts = [item[1] for item in batch]
    records = [item[0] for item in batch]
    outputs: List[str] = [""] * len(batch)

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as ex:
        fut2idx = {ex.submit(_call_llm_api, p, model, client): i for i, p in enumerate(prompts)}
        for fut in concurrent.futures.as_completed(fut2idx):
            idx = fut2idx[fut]
            try:
                outputs[idx] = fut.result()
            except Exception as exc:  # noqa: BLE001
                outputs[idx] = f"API 调用失败: {exc}"

    return list(zip(records, outputs))


def _run_evaluation(dataset: Path, output: Path, model: str, limit: int | None) -> None:
    """Query *model* on *dataset* and write augmented records to *output*."""
    already_done = _count_lines(output) if output.exists() else 0
    total_lines = _count_lines(dataset)

    to_process = total_lines - already_done
    if limit is not None:
        to_process = min(to_process, limit)

    mode = "a" if already_done else "w"
    print(f"已存在 {already_done} 条，待处理 {to_process} 条（总 {total_lines} 条）")

    # --- construct OpenAI client once ---
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AIHUBMIX_API")
    if not api_key:
        raise EnvironmentError("请先设置环境变量 OPENAI_API_KEY 或 AIHUBMIX_API")
    client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL"))

    with dataset.open("r", encoding="utf-8") as fin, output.open(mode, encoding="utf-8") as fout, tqdm(
        total=already_done + to_process, initial=already_done, unit="条", desc="评测"
    ) as pbar:
        # skip already processed lines
        for _ in range(already_done):
            next(fin)

        batch: List[Tuple[dict[str, Any], str]] = []
        processed = 0
        for line_no, line in enumerate(fin, start=already_done + 1):
            if processed >= to_process:
                break
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)
            if not all(k in record for k in ("question", "A", "B", "C", "D", CORRECT_LABEL_FIELD)):
                record[TARGET_FIELD_NAME] = "Skipped: 缺少字段"
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                pbar.update(1)
                processed += 1
                continue

            prompt = _build_prompt(
                record["question"],
                {"a": record["A"], "b": record["B"], "c": record["C"], "d": record["D"]},
            )
            batch.append((record, prompt))

            if len(batch) >= CONCURRENT_REQUESTS:
                for rec, ans in _process_batch(batch, model, client):
                    rec[TARGET_FIELD_NAME] = ans
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fout.flush()
                pbar.update(len(batch))
                processed += len(batch)
                batch.clear()

        # flush remainder
        if batch:
            for rec, ans in _process_batch(batch, model, client):
                rec[TARGET_FIELD_NAME] = ans
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            pbar.update(len(batch))



def _analyze_output(path: Path, id_field: str | None) -> None:
    correct_idx, wrong_idx, unparsed_idx = [], [], []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            rec = json.loads(line)
            prediction = _parse_option(rec.get(TARGET_FIELD_NAME, ""))
            gt = str(rec.get(CORRECT_LABEL_FIELD, "")).lower()

            identifier = rec.get(id_field, line_no) if id_field else line_no

            if prediction is None:
                unparsed_idx.append(identifier)
            elif prediction == gt:
                correct_idx.append(identifier)
            else:
                wrong_idx.append(identifier)

    total = len(correct_idx) + len(wrong_idx) + len(unparsed_idx)
    acc = len(correct_idx) / total * 100 if total else 0.0

    print("\n====== 评测统计 ======")
    print(f"总记录数           : {total}")
    print(f"  ✔ 正确           : {len(correct_idx)}")
    print(f"  ✘ 错误           : {len(wrong_idx)}")
    print(f"  - 解析失败        : {len(unparsed_idx)}")
    print(f"\n总体准确率         : {acc:.2f}%")

    print("\n正确索引列表:")
    print(", ".join(map(str, correct_idx)) or "（空）")

    print("\n错误索引列表:")
    print(", ".join(map(str, wrong_idx)) or "（空）")

    if unparsed_idx:
        print("\n未解析索引列表:")
        print(", ".join(map(str, unparsed_idx)))


def main() -> None:
    parser.add_argument("--dataset", required=True, help="输入 JSONL 数据集文件")
    parser.add_argument("--model", required=True, help="OpenAI 模型名称 (如 gpt-4o)")
    parser.add_argument("--output", required=True, help="输出 JSONL 文件")
    parser.add_argument("--id_field", help="记录唯一标识字段名 (可选)")
    parser.add_argument("--limit", type=int, help="仅测试前 N 条 (可选)")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)

    _run_evaluation(dataset_path, output_path, args.model, args.limit)
    _analyze_output(output_path, args.id_field)


if __name__ == "__main__":
    main()
