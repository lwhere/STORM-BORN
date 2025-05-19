import sys
import os
import argparse
from argparse import Namespace
import time
import json
import PIL.Image
import google.generativeai as genai
import typing_extensions as typing
import time

genai.configure(api_key="your_key")

def call_LLM_model(prompt, pdf_path, data):
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    # model3 = genai.GenerativeModel("gemini-2.0-flash-thinking-exp")
    sample_pdf = genai.upload_file(pdf_path)
    response3 = model.generate_content([sample_pdf, prompt, data], generation_config=genai.types.GenerationConfig(temperature=0.0,),request_options={"timeout": 600})
    return response3.text

def refine(input_path, pdf_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    prompt = """我刚刚发送了一篇论文供你阅读，并将在随后提供一个 JSON 格式的数据，为一个字典。你的任务是对数据中的内容进行阅读理解，并基于以下步骤进行处理：

1. **解析需求**：“query”是一个数学证明推导的问题，其中提到了数学表达式、定理、引理、相关前提条件、定义以及问题目标，"query_evidence"是“query”的内容在论文中对应的原文。
2. **解析需求**：“whole_label”是从论文找到的“query”的答案，是一个证明推导过程。“whole_label_evidence”是“whole_label”的内容在论文中对应的原文。
3. **重构问题**：问题“query”中的前提条件等可能有遗漏，缺少背景知识、相关数学表达式或字符的定义。请你根据1.和2.的解析结果，重构问题“query”，补充缺少的前提条件、相关定义。确保新的问题和答案是self-contained，不需借助原论文也能看懂，新的问题为英文。latex格式可以使用 \` 表示反斜杠，\n 表示换行符。**禁止使用 `\_` 或任何其他非 JSON 标准的转义字符。请确保latex格式的数学表达式是有效的 JSON 对象，能够被 `json.loads()` 正确解析。然后将每段连续的原文作为一个元素。所有元素组成一个列表。
4. **计录数据**：以jsonl格式记录下来：
   - 键为 "question"。
   - 值为第3步重构的新的问题结果，注意内容为英文。
5. **输出结果**：以 JSONL 格式输出第4步更新的jsonl数据，确保数据只占一行，不允许跨行。
提供的 JSON 格式的数据集如下（按照以上的要求处理数据）：\n"""#question_refiner
    output_path = os.path.join(output_dir, "api_"+ pdf_path.split('\\')[-1][:-4]+"_question.jsonl")
    # output_path = os.path.join(output_dir, os.path.basename(input_path).split('\\')[-1][:-4]+"_question.jsonl")
    failed_lines = []
    max_retries = 5
    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        lines = infile.readlines()

        for line in lines:
            retries = 0
            while retries < max_retries:
                data = json.loads(line.strip())
                data_ = {}
                data_["query"] = data["query"]
                data_["whole_label"] = data["whole_label"]
                data_["query_evidence"] = data["query_evidence"]
                data_["whole_label_evidence"] = data["whole_label_evidence"]
                result = call_LLM_model(prompt, pdf_path, json.dumps(data_))
                # print(result)
                try:
                    # assert 0
                    result = result.strip("```jsonl\n")
                    # print("llm done")
                    result = json.loads(result)
                    data["question"] = result["question"]
                    one_line_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
                    outfile.write(one_line_json + "\n")
                    break
                except Exception as e:
                    retries += 1
                    time.sleep(2 ** retries)  # Exponential backoff
                    print(f"Retrying ({retries}/{max_retries}) for line due to error: {e}")
                    if retries == max_retries:
                        failed_lines.append(line)

    if failed_lines:
        failed_path = os.path.join(output_dir, os.path.basename(input_path) + '_failed-question.jsonl')
        with open(failed_path, 'w', encoding='utf-8') as fail_file:
            fail_file.writelines(failed_lines)
        print(f"Failed lines saved to: {failed_path}")

    print(f"Processed file saved to: {output_path}")
    return output_path



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_path', type=str, default="E:\dmt\\formula\\Direct Preference Optimization--Your Language Model is Secretly a Reward Mode.pdf", help='the input file path')
    parser.add_argument('--model_name', type=str, default="gemini-2.0-flash-exp", help='the gemini model you want to use.')
    parser.add_argument('--input_path', type=str, default="E:\\dmt\\formula\\generated\\final_test\\api_Direct Preference Optimization--Your Language Model is Secretly a Reward Mode_query.j_context.jsonl", help='input QA with context(.jsonl)')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated\\final_test", help='output dir')
    args = parser.parse_args()
    print("pdf: " + args.pdf_path)
    print("model: " + args.model_name)
    print("input QA+context(.jsonl): " + args.input_path)
    print("output_dir: " + args.output_dir)

    

    refine(args.input_path, args.pdf_path, args.output_dir)

   
