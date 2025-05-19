import os
import json
from openai import OpenAI
import argparse
from argparse import Namespace

# 配置 OpenAI API 密钥
# openai.api_key = 'your_openai_api_key_here'


def call_deepseek_model(prompt, data, model_name):
    """
    调用 deepseek 大模型，判断输出是 derive 还是 define。
    :param prompt: 输入 prompt
    :param data: 当前处理的数据
    :return: deepseek 模型的输出 (derive 或 define)
    """
    try:
        client = OpenAI(
            # #将这里换成你在aihubmix api keys拿到的密钥
            api_key="sk-ORipmtAUfrC6oP0z146f73Df2b9748558090Aa366b491046",
            # 这里将官方的接口访问地址，替换成aihubmix的入口地址
            base_url="https://api.aihubmix.com/v1"
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a reasoning assistant."},
                {"role": "user", "content": f"{prompt}\n{data}"}
            ],
            model=model_name,
        )
        output = chat_completion.choices[0].message.content
        print(output)
        print(output.split('\n')[0].lower())
        
        if "derive" in output:
            return "derive"
        elif "define" in output:
            return "define"
        else:
            return None
        # print(chat_completion)
        # assert 0
        # response = openai.ChatCompletion.create(
        #     model="gpt-4",  # 使用 deepseek 或指定模型
        #     messages=[
        #         {"role": "system", "content": "You are a reasoning assistant."},
        #         {"role": "user", "content": f"{prompt}\n{data}"}
        #     ]
        # )
        # output = response["choices"][0]["message"]["content"].strip().lower()
        # return output
    except Exception as e:
        print(f"Error calling model: {e}")
        return None

def filter_jsonl(input_path, output_dir, model):
    """
    过滤 JSONL 文件中的数据，只保留 derive 数据。
    :param input_path: 输入 JSONL 文件路径
    :param output_dir: 输出文件保存的目录
    :param prompt: 调用 deepseek 模型的 prompt
    """
    prompt = "请你判断，这里面的问答对（question-whole_label）中，whole_label的内容是推导、证明一类的回答（输出\"derive!\"），还是简单的定义、引用一类的回答（输出\"define!\"）。必须先输出以下类型之一\"derive!\"或者\"define!\"，然后再输出解释。"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join(output_dir, "final_"+os.path.basename(input_path))
    # output_path = os.path.join(output_dir, os.path.basename(input_path))

    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        n = 0
        for line in infile:
            n = n+1
            print(n)
            data = json.loads(line.strip())
            result = call_deepseek_model(prompt, json.dumps(data), model)
            print(result)
            if result == "derive":
                outfile.write(json.dumps(data, ensure_ascii=False) + "\n")
            print("***"*20)

    print(f"Filtered data saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_name', type=str, default="deepseek-chat", help='the deepseek model you want to use.')
    parser.add_argument('--input_path', type=str, default="E:\dmt\\formula\generated\\final_test\\api_Direct Preference Optimization--Your Language Model is Secretly a Reward Mode_question.jsonl", help='input QA with question(.jsonl)')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated\\final_test", help='output dir')
    args = parser.parse_args()
    print("model: " + args.model_name)
    print("input data with question(.jsonl): " + args.input_path)
    print("output_dir: " + args.output_dir)


    

    filter_jsonl(args.input_path, args.output_dir, args.model_name)