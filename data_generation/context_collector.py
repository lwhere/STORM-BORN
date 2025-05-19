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
    response3 = model.generate_content([sample_pdf, prompt, data], generation_config=genai.types.GenerationConfig(temperature=0.05,),request_options={"timeout": 600})
    return response3.text

def context_collect(input_path, pdf_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    prompt = """我刚刚发送了一篇论文供你阅读，并将在随后提供一个 JSON 格式的数据，为一个字典。你的任务是对数据中的内容进行阅读理解，并基于以下步骤进行处理：

1. **解析需求**：根据“query”中提到的数学表达式、定理、引理、相关前提条件、定义以及问题目标，找到这些内容在论文中对应的原文。如果原文内容引用了其他的公式、定理、引理、定义等，明确列出这些公式的完整内容并放在对应的引用后。
2. **格式化内容**：将找到的论文原文提取出来，保持与原文一致的段落连续性，如果提取的内容引用了其他的公式、定理、引理、定义等，请找到这些公式的完整内容并放在引用后，并将所有数学表达式转化为 query 中的 LaTeX 格式。latex格式可以使用 \\ 表示反斜杠，\n 表示换行符。**禁止使用 `\_` 或任何其他非 JSON 标准的转义字符。请确保latex格式的数学表达式是有效的 JSON 对象，能够被 `json.loads()` 正确解析。然后将每段连续的原文作为一个元素。所有元素组成一个列表。
3. **计录数据**：以jsonl格式记录下来：
   - 键为 "query_evidence"。
   - 值为第2步提取到的论文原文组成的列表。注意列表格式正确，[]里面每个元素为一个字符串，是第2步中提取的原文片段。
然后你还需要：
4. **解析需求**：根据“whole_label”中的证明推导过程以及提到的数学表达式、定理、引理、相关前提条件、定义，找到这些内容在论文中对应的原文。如果原文内容引用了其他的公式、定理、引理、定义等，明确列出这些公式的完整内容并放在对应的引用后。
5. **格式化内容**：将找到的论文原文提取出来，保持与原文一致的段落连续性，如果提取的内容引用了其他的公式、定理、引理、定义等，请找到这些公式的完整内容并放在引用后，并将所有数学表达式转化为 whole_lable 中的 LaTeX 格式。latex格式可以使用 \\ 表示反斜杠，\n 表示换行符。**禁止使用 `\_` 或任何其他非 JSON 标准的转义字符。请确保latex格式的数学表达式是有效的 JSON 对象，能够被 `json.loads()` 正确解析。然后将每段连续的原文作为一个元素。所有元素组成一个列表。
6. **更新计录数据**：在第3步记录的数据中新增一个键值对：
   - 键为 "whole_label_evidence"。
   - 值为第5步提取到的论文原文组成的列表。注意列表格式正确，[]里面每个元素为一个字符串，是第2步中提取的原文片段。
7. **输出结果**：以 JSONL 格式输出第6步更新的jsonl数据，确保数据只占一行，不允许跨行。
提供的 JSON 格式的数据集如下（按照以上的要求处理数据）：\n"""#context_collector
    output_path  = os.path.join(output_dir, "api_"+ pdf_path.split('\\')[-1][:-4]+"_context.jsonl")
    # output_path = os.path.join(output_dir, os.path.basename(input_path).split('\\')[-1][:-4]+"_context.jsonl")
    max_retries = 5
    failed_lines = []

    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        lines = infile.readlines()

        for line in lines:
            retries = 0
            while retries < max_retries:
                
                data = json.loads(line.strip())
                data_ = {}
                data_["query"] = data["query"]
                data_["whole_label"] = data["whole_label"]
                result = call_LLM_model(prompt, pdf_path, json.dumps(data_))
                # print(result)
                # print("llm done")
                try:
                    result = result.strip("```jsonl\n")
                    result = json.loads(result)
                    data["query_evidence"] = result["query_evidence"]
                    data["whole_label_evidence"] = result["whole_label_evidence"]
                    one_line_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
                    outfile.write(one_line_json + "\n")
                    break
                except Exception as e:
                    print(result)
                    retries += 1
                    time.sleep(2 ** retries)  # Exponential backoff
                    print(f"Retrying ({retries}/{max_retries}) for line due to error: {e}")
                    if retries == max_retries:
                        failed_lines.append(line)

    if failed_lines:
        failed_path = os.path.join(output_dir, os.path.basename(input_path) + '_failed-context.jsonl')
        with open(failed_path, 'w', encoding='utf-8') as fail_file:
            fail_file.writelines(failed_lines)
        print(f"Failed lines saved to: {failed_path}")
    
    print(f"Processed file saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_path', type=str, default="E:\dmt\\formula\\Direct Preference Optimization--Your Language Model is Secretly a Reward Mode.pdf", help='the input file path')
    parser.add_argument('--model_name', type=str, default="gemini-2.0-flash-exp", help='the gemini model you want to use.')
    parser.add_argument('--input_path', type=str, default="E:\\dmt\\formula\\generated\\final_test\\api_Direct Preference Optimization--Your Language Model is Secretly a Reward Mode_QA.jsonl", help='input QA(.jsonl)')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated\\final_test", help='output dir')
    args = parser.parse_args()
    print("pdf: " + args.pdf_path)
    print("model: " + args.model_name)
    print("input QA(.jsonl): " + args.input_path)
    print("output_dir: " + args.output_dir)

    

    context_collect(args.input_path, args.pdf_path, args.output_dir)

   
