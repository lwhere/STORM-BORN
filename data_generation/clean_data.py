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
    "You are a helpful dataset cleaner. The user will provide instruction and output (both in latex format). Please clean them and output the latex formatted instruction and output in JSON wrapper.\n"
    r"""
    1. Removed redundant references to external sources ("the paper/Section/Page/cref, etc."), make sure the output and instruction is self contained.
    2. Fixed LaTeX formatting (proper escaping of special characters), avoid markdown symbol like `*', convert Chinese to English. 
    3. Structured the output as a clear reasoning process, try to retain more human thinking process and derivations.  
    4. Ensured the output contains main derivations as answer and instruction donnot contains main derivations, but also need has enough formula to be a self-contained question.
    6. Organized in the requested JSON format with only instruction/output key-value.
    """
)


def clean_data():
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


clean_data()