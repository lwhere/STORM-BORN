import json
import os
import re
import hashlib
import unittest
from unittest.mock import patch, MagicMock
import io

def get_sub_label_from_llm(client, whole_label: str) -> str:
    system_prompt = (
        "You are an expert in mathematical and scientific explanations. Your task is to break down a given "
        "detailed explanation ('whole_label') into a series of logical, step-by-step sub-explanations.\n\n"
        "You MUST format the output as a single string. Each individual step of the explanation MUST be "
        "enclosed in <sub_label></sub_label> tags. Do not add any other text, numbering, or formatting "
        "outside of these tags. You should also convert equations into <derivation></derivation>"
        "Now, process the following input:\n"
        f"{{whole_label}}"
    )

    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash-lite",
            messages=[
                {"role": "system", "content": system_prompt.format(whole_label=whole_label)}
            ],
            temperature=0.0,
            max_tokens=10240,
        )
        content = response.choices[0].message.content
        if content and content.startswith("```") and content.endswith("```"):
            content = content[3:-3]
        if content and content.startswith("`") and content.endswith("`"):
            content = content[1:-1]
        return content.strip()
    except Exception as e:
        print(f"调用LLM时发生错误: {e}")
        return "<sub_label>无法生成子标签</sub_label>"

def divide_sublabel_module(input_path: str, output_path: str, final_output_path: str, client):
    print("--- 开始执行模块一: 分解标签并实时生成完形填空 ---")
    
    all_fill_blanks = []
    
    try:
        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', encoding='utf-8') as sub_label_outfile, \
             open(final_output_path, 'w', encoding='utf-8') as final_outfile:
            
            line_count = 0
            for line in infile:
                line_count += 1
                try:
                    data = json.loads(line)
                    question = data.get("question")
                    whole_label = data.get("whole_label")

                    if question is None or whole_label is None:
                        print(f"第 {line_count} 行: 跳过缺少'question'或'whole_label'的行。")
                        continue

                    print(f"第 {line_count} 行: 正在处理...")
                    sub_label_content = get_sub_label_from_llm(client, whole_label)

                    if not sub_label_content.startswith("<sub_label>"):
                         sub_label_content = f"<sub_label>{sub_label_content}</sub_label>"

                    module1_output_data = {
                        "paper": data.get("paper"),
                        "question": question,
                        "whole_label": whole_label,
                        "sub_label": sub_label_content
                    }
                    
                    sub_label_outfile.write(json.dumps(module1_output_data, ensure_ascii=False) + '\n')
                    print(f"第 {line_count} 行: sub_label处理完成。")
                    
                    print(f"第 {line_count} 行: 正在生成完形填空...")
                    fill_blanks = generate_fill_in_the_blanks(module1_output_data)
                    
                    for fill_blank_item in fill_blanks:
                        final_outfile.write(json.dumps(fill_blank_item, ensure_ascii=False) + '\n')
                        all_fill_blanks.append(fill_blank_item)
                    
                    print(f"第 {line_count} 行: 生成了 {len(fill_blanks)} 条完形填空数据。")

                except json.JSONDecodeError:
                    print(f"第 {line_count} 行: 跳过无效的JSON行。")
                except Exception as e:
                    print(f"第 {line_count} 行: 处理时发生未知错误: {e}")
                    
        print(f"总共生成了 {len(all_fill_blanks)} 条完形填空数据")
        
    except FileNotFoundError:
        print(f"错误: 输入文件 '{input_path}' 未找到。")
    except Exception as e:
        print(f"处理文件时发生重大错误: {e}")
    print("--- 模块一执行完毕 ---\n")


def generate_fill_in_the_blanks(data: dict) -> list:
    sub_label = data.get("sub_label", "")
    question_text = data.get("question", "")
    
    derivation_pattern = r"<derivation>(.*?)</derivation>"
    derivations = re.findall(derivation_pattern, sub_label, re.DOTALL)
    
    processed_derivations = set()
    final_output_list = []

    for derivation in derivations:
        cleaned_derivation = derivation.strip()
        if cleaned_derivation in processed_derivations:
            continue
            
        full_derivation_tag = f"<derivation>{cleaned_derivation}</derivation>"
        blank_answer = sub_label.replace(full_derivation_tag, "[MASKED_DERIVATION]", 1)
        
        content_for_hash = question_text + cleaned_derivation
        h = hashlib.sha256(content_for_hash.encode('utf-8')).hexdigest()
        
        final_output_list.append({
            "question": question_text,
            "ground_truth": f"<derivation>{cleaned_derivation}</derivation>",
            "blank_answer": blank_answer,
            "hash": h
        })
        processed_derivations.add(cleaned_derivation)
    return final_output_list

def mask_sublabel_module(input_path: str, output_path: str):
    print("--- 开始执行模块二: 生成完形填空 (独立模式) ---")
    generated_questions = []
    try:
        with open(input_path, "r", encoding="utf-8") as infile:
            for line in infile:
                try:
                    data = json.loads(line)
                    generated_questions.extend(generate_fill_in_the_blanks(data))
                except json.JSONDecodeError:
                    print(f"跳过无效的JSON行: {line.strip()}")

        with open(output_path, 'w', encoding='utf-8') as outfile:
            for item in generated_questions:
                outfile.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        print(f"成功生成 {len(generated_questions)} 条完形填空数据并保存到 '{output_path}'")

    except FileNotFoundError:
        print(f"错误: 输入文件 '{input_path}' 未找到。")
    except Exception as e:
        print(f"处理文件时发生重大错误: {e}")
    print("--- 模块二执行完毕 ---\n")


class TestDataProcessingPipeline(unittest.TestCase):
    def setUp(self):
        self.module1_input_data = {
            "paper": "arxiv:1234.5678",
            "question": "这是一个问题。",
            "whole_label": "第一步是A。<derivation>A=B</derivation>。第二步是C。<derivation>C=D</derivation>。"
        }
        
        self.module2_input_data = {
            "paper": "arxiv:1234.5678",
            "question": "这是一个问题。",
            "whole_label": "第一步是A。<derivation>A=B</derivation>。第二步是C。<derivation>C=D</derivation>。",
            "sub_label": "<sub_label>第一步是A。<derivation>A=B</derivation></sub_label><sub_label>第二步是C。<derivation>C=D</derivation></sub_label>"
        }

    def test_module1_divide_sublabel_output_format(self):
        print("\n--- 正在运行测试: test_module1_divide_sublabel_output_format ---")
        
        mock_llm_response = "<sub_label>这是模拟的子标签1。</sub_label><sub_label>这是模拟的子标签2。<derivation>E=F</derivation></sub_label>"
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = mock_llm_response
        mock_client.chat.completions.create.return_value = mock_response

        input_file = io.StringIO(json.dumps(self.module1_input_data) + '\n')
        input_file.name = "mock_input.jsonl" 
        sub_label_output_file = io.StringIO()
        sub_label_output_file.name = "mock_sub_label_output.jsonl"
        final_output_file = io.StringIO()
        final_output_file.name = "mock_final_output.jsonl"

        with patch('builtins.open', side_effect=lambda file, *args, **kwargs: {
            "mock_input.jsonl": input_file, 
            "mock_sub_label_output.jsonl": sub_label_output_file,
            "mock_final_output.jsonl": final_output_file
        }[file]):
            divide_sublabel_module("mock_input.jsonl", "mock_sub_label_output.jsonl", "mock_final_output.jsonl", mock_client)

        sub_label_output_file.seek(0)
        sub_label_result_line = sub_label_output_file.read()
        self.assertTrue(sub_label_result_line, "模块一的sub_label输出文件不应为空")
        
        sub_label_result_data = json.loads(sub_label_result_line)
        self.assertIn("paper", sub_label_result_data)
        self.assertIn("question", sub_label_result_data)
        self.assertIn("whole_label", sub_label_result_data)
        self.assertIn("sub_label", sub_label_result_data)
        self.assertEqual(sub_label_result_data["sub_label"], mock_llm_response)
        
        final_output_file.seek(0)
        final_result_lines = final_output_file.read().strip().split('\n')
        self.assertTrue(len(final_result_lines) > 0, "最终输出文件不应为空")
        
        mock_client.chat.completions.create.assert_called_once()
        print("--- 测试通过 ---")


    def test_module2_mask_sublabel_output_format(self):
        print("\n--- 正在运行测试: test_module2_mask_sublabel_output_format ---")
        
        results = generate_fill_in_the_blanks(self.module2_input_data)
        
        self.assertIsInstance(results, list, "输出应为一个列表")
        self.assertEqual(len(results), 2, "应为每个derivation生成一个条目")

        item1 = results[0]
        self.assertIn("question", item1)
        self.assertIn("ground_truth", item1)
        self.assertIn("blank_answer", item1)
        self.assertIn("hash", item1)
        
        self.assertEqual(item1["ground_truth"], "<derivation>A=B</derivation>")
        self.assertIn("[MASKED_DERIVATION]", item1["blank_answer"])
        self.assertNotIn("<derivation>A=B</derivation>", item1["blank_answer"])
        
        item2 = results[1]
        self.assertEqual(item2["ground_truth"], "<derivation>C=D</derivation>")
        self.assertIn("[MASKED_DERIVATION]", item2["blank_answer"])
        self.assertNotIn("<derivation>C=D</derivation>", item2["blank_answer"])
        print("--- 测试通过 ---")

    def test_pipeline_data_flow_integration(self):
        print("\n--- 正在运行测试: test_pipeline_data_flow_integration ---")
        
        module1_output = self.module2_input_data # 使用预设的模拟数据
        
        module2_results = generate_fill_in_the_blanks(module1_output)
        
        self.assertTrue(len(module2_results) > 0, "模块二未能从模块一的输出中生成任何数据")
        self.assertEqual(len(module2_results), 2, "数据流整合测试失败，未生成预期数量的结果")
        
        print("--- 测试通过 ---")


if __name__ == "__main__":
    def setup_example_input_file(filename='storm-born.jsonl'):
        if not os.path.exists(filename):
            print(f"输入文件 '{filename}' 不存在，正在创建示例文件...")
            jsonl_data = {"paper":"arxiv:2305.18290", "question":"Given the formula, prove the optimal solution.", "whole_label":"To derive the optimal solution, we start by considering the optimization problem. <derivation>\\max_{\\pi}  \\mathbb{E}_{x\\sim \\mathcal{D}, y\\sim \\pi}\\bigl[r(x, y)\\bigr] - \\beta\\mathbb{D}_{\\textrm{KL}}\\bigl[\\pi(y|x)||\\pi_{\\text{ref}}(y|x)\\bigr].\\end{equation}</derivation> This can be rewritten as a minimization problem. <derivation>\\min_{\\pi}  \\mathbb{E}_{x\\sim \\mathcal{D}}\\mathbb{E}_{y\\sim \\pi(y|x)}\\left[\\log\\frac{\\pi(y|x)}{\\pi_{\\text{ref}}(y|x)} - \\frac{1}{\\beta}r(x, y)\\right].\\end{align}</derivation>"}
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json.dumps(jsonl_data) + '\n')
            print(f"示例输入文件 '{filename}' 已创建。")

    def run_pipeline():
        client = None 

        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("AIHUBMIX_API_KEY"),
            base_url="https://aihubmix.com/v1"
        )

        if not client:
            print("错误：OpenAI客户端未配置。无法运行 `run_pipeline`。")
            print("请在代码中配置您的 `api_key` 和 `base_url`。")
            return

        input_filename = 'storm-born.jsonl'
        sub_label_output_filename = 'storm_born_divide_sublabel_output.jsonl'
        final_output_filename = 'fill_in_the_blanks_storm_born_data.jsonl'
        
        setup_example_input_file(input_filename)
        
        divide_sublabel_module(input_filename, sub_label_output_filename, final_output_filename, client)
        
        print("流水线执行完毕！")

    
    def run_tests():
        print("=========================================")
        print("          开始运行单元测试         ")
        print("=========================================")
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestDataProcessingPipeline))
        runner = unittest.TextTestRunner()
        runner.run(suite)

    print("--- 准备执行生产流程 ---")
    run_pipeline()

    print("\n")
    
