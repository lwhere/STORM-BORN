import json

def to_json(data, file_path):
    with open(file_path, 'a') as f:
        json.dump(data, f)

def to_jsonl(data, file_path):
    with open(file_path, 'a') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')

# json2jsonl("tmp.json", "tmp.jsonl")
import json
from openai import OpenAI

client = OpenAI(
    api_key="sk-xx",
    base_url="https://api.deepseek.com",
)

system_prompt = (
    "You are a precise mathematical proof evaluator for proof problems. The user will provide both a problem statement, ground truth proof and a proposed solution. Evaluate the solution based on the ground truth proof, score the solution based on the following criteria:"
    r"""
    1. **Correctness (0-2):**
    - 0: Fundamentally wrong.
    - 1: Partially correct with significant flaws.
    - 2: Fully correct and logically sound.

    2. **Clarity (0-2):**
    - 0: Low clarity; poor logical flow and explanation.
    - 1: Medium clarity; somewhat understandable but lacking detail.
    - 2: High clarity; well-explained and logically structured.

    3. **Completeness (0-2):**
    - 0: Incomplete; key steps are missing.
    - 1: Moderately complete; some steps or justifications are missing.
    - 2: Fully complete; all necessary steps and justifications are present.

    4. **Similarity (0-2):**
    - 0: No similarity; completely different from the ground truth.
    - 1: Some similarity; some steps or justifications are similar.
    - 2: High similarity; all steps and justifications are identical.

    Output your evaluation as a JSON object in the format:
    {"correctness": <0-2>, "clarity": <0-2>, "completeness": <0-2>, "similarity": <0-2>} 
    """
)


def llm_evaluate():
    jsonl_file = 'tmp.jsonl'
    with open(jsonl_file, 'r') as f:
        data = [json.loads(line) for line in f]

    new_data, failed_data = [], []
    for da in data:

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": "{\"instruction\":" + da['instruction'] + ", \"output\":" + da['output'] + "}\n"}]
        for _ in range(3):
            print(messages)
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=1,
                response_format={
                    'type': 'json_object'
                }
            )
            try:
                content = json.loads(response.choices[0].message.content)
                print('---'*30)
                print(content)
                print('---'*30)
                new_data.append(content)
                break
            except:
                pass
        else:
            failed_data.append(da)
            print("failed")

    to_jsonl(new_data, "new_data.jsonl")
    to_jsonl(failed_data, "failed_data.jsonl")


llm_evaluate()