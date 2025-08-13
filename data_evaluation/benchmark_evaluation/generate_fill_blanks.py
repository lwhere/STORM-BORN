# -*- coding: utf-8 -*-
"""
一个集成的Python脚本，用于执行两步数据处理流程：
1.  第一步 (divide_sublabel_module): 调用大语言模型（LLM）将一个完整的解释文本分解为多个子步骤。
2.  第二步 (mask_sublabel_module): 基于第一步的输出，为其中的每个推导步骤（derivation）创建"完形填空"式的问题。

该脚本还包含一个独立的单元测试套件，用于验证每个模块的功能和数据交付格式的正确性。
"""

import json
import os
import re
import hashlib
import unittest
from unittest.mock import patch, MagicMock
import io

# =======================================================================
# 模块一: 分解标签 (Refactored from divide_sublabel.py)
# =======================================================================

def get_sub_label_from_llm(client, whole_label: str) -> str:
    """
    调用符合OpenAI协议的LLM将whole_label分解为被<sub_label>包裹的步骤。

    Args:
        client: OpenAI API的客户端实例。
        whole_label: 完整的解释字符串。

    Returns:
        由LLM生成的、被标签包裹的分解步骤字符串。
    """
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
    """
    读取JSONL文件，为每一行调用LLM进行处理，并实时调用mask操作生成完形填空数据。

    Args:
        input_path: 输入的JSONL文件路径。
        output_path: 中间输出的JSONL文件路径（sub_label结果）。
        final_output_path: 最终输出的JSONL文件路径（完形填空结果）。
        client: OpenAI API的客户端实例。
    """
    print("--- 开始执行模块一: 分解标签并实时生成完形填空 ---")
    
    # 用于收集所有生成的完形填空数据
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

                    # 确保输出格式的健壮性
                    if not sub_label_content.startswith("<sub_label>"):
                         sub_label_content = f"<sub_label>{sub_label_content}</sub_label>"

                    # 构建模块一的输出数据
                    module1_output_data = {
                        "paper": data.get("paper"),
                        "question": question,
                        "whole_label": whole_label,
                        "sub_label": sub_label_content
                    }
                    
                    # 写入中间结果文件
                    sub_label_outfile.write(json.dumps(module1_output_data, ensure_ascii=False) + '\n')
                    print(f"第 {line_count} 行: sub_label处理完成。")
                    
                    # 实时调用mask操作
                    print(f"第 {line_count} 行: 正在生成完形填空...")
                    fill_blanks = generate_fill_in_the_blanks(module1_output_data)
                    
                    # 写入最终结果文件
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


# =======================================================================
# 模块二: 生成完形填空 (Refactored from mask_sublabel.py)
# =======================================================================

def generate_fill_in_the_blanks(data: dict) -> list:
    """
    针对单个输入数据，为sub_label中的每个<derivation>生成一个完形填空问题。

    Args:
        data: 包含 "question" 和 "sub_label" 键的字典。

    Returns:
        一个包含多个字典的列表，每个字典都是一个完形填空问题。
    """
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
        # 使用 [MASK] 作为占位符，更符合常规
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
    """
    读取模块一的输出文件，为每一行生成完形填空问题，并写入最终的JSONL文件。
    这个函数现在主要用于处理已有的sub_label文件，实时处理已经在divide_sublabel_module中实现。

    Args:
        input_path: 输入的JSONL文件路径 (来自模块一的输出)。
        output_path: 最终输出的JSONL文件路径。
    """
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


# =======================================================================
# 单元测试模块 (Unit Test Section)
# =======================================================================

class TestDataProcessingPipeline(unittest.TestCase):
    """
    针对重构后代码的单元测试，验证每个模块的数据格式和核心功能。
    """

    def setUp(self):
        """测试前的准备工作"""
        # 模块一的模拟输入数据
        self.module1_input_data = {
            "paper": "arxiv:1234.5678",
            "question": "这是一个问题。",
            "whole_label": "第一步是A。<derivation>A=B</derivation>。第二步是C。<derivation>C=D</derivation>。"
        }
        
        # 模块二的模拟输入数据（即模块一的模拟输出）
        self.module2_input_data = {
            "paper": "arxiv:1234.5678",
            "question": "这是一个问题。",
            "whole_label": "第一步是A。<derivation>A=B</derivation>。第二步是C。<derivation>C=D</derivation>。",
            "sub_label": "<sub_label>第一步是A。<derivation>A=B</derivation></sub_label><sub_label>第二步是C。<derivation>C=D</derivation></sub_label>"
        }

    def test_module1_divide_sublabel_output_format(self):
        """
        测试模块一 (divide_sublabel_module) 的输出数据格式是否正确。
        - 使用 mock 模拟 LLM API 调用。
        - 使用 io.StringIO 模拟文件读写。
        """
        print("\n--- 正在运行测试: test_module1_divide_sublabel_output_format ---")
        
        # 模拟LLM返回的内容
        mock_llm_response = "<sub_label>这是模拟的子标签1。</sub_label><sub_label>这是模拟的子标签2。<derivation>E=F</derivation></sub_label>"
        
        # 创建模拟的OpenAI客户端
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = mock_llm_response
        mock_client.chat.completions.create.return_value = mock_response

        # 模拟输入和输出文件
        input_file = io.StringIO(json.dumps(self.module1_input_data) + '\n')
        input_file.name = "mock_input.jsonl" # 赋予一个名字以模拟真实文件
        sub_label_output_file = io.StringIO()
        sub_label_output_file.name = "mock_sub_label_output.jsonl"
        final_output_file = io.StringIO()
        final_output_file.name = "mock_final_output.jsonl"

        # 使用 patch 来临时替换 open 函数
        with patch('builtins.open', side_effect=lambda file, *args, **kwargs: {
            "mock_input.jsonl": input_file, 
            "mock_sub_label_output.jsonl": sub_label_output_file,
            "mock_final_output.jsonl": final_output_file
        }[file]):
            divide_sublabel_module("mock_input.jsonl", "mock_sub_label_output.jsonl", "mock_final_output.jsonl", mock_client)

        # 检查sub_label输出
        sub_label_output_file.seek(0)
        sub_label_result_line = sub_label_output_file.read()
        self.assertTrue(sub_label_result_line, "模块一的sub_label输出文件不应为空")
        
        # 验证sub_label输出的数据结构
        sub_label_result_data = json.loads(sub_label_result_line)
        self.assertIn("paper", sub_label_result_data)
        self.assertIn("question", sub_label_result_data)
        self.assertIn("whole_label", sub_label_result_data)
        self.assertIn("sub_label", sub_label_result_data)
        self.assertEqual(sub_label_result_data["sub_label"], mock_llm_response)
        
        # 检查最终输出
        final_output_file.seek(0)
        final_result_lines = final_output_file.read().strip().split('\n')
        self.assertTrue(len(final_result_lines) > 0, "最终输出文件不应为空")
        
        # 验证API是否被正确调用
        mock_client.chat.completions.create.assert_called_once()
        print("--- 测试通过 ---")


    def test_module2_mask_sublabel_output_format(self):
        """
        测试模块二 (generate_fill_in_the_blanks) 的输出数据格式是否正确。
        """
        print("\n--- 正在运行测试: test_module2_mask_sublabel_output_format ---")
        
        # 直接调用核心函数进行测试
        results = generate_fill_in_the_blanks(self.module2_input_data)
        
        # 验证结果
        self.assertIsInstance(results, list, "输出应为一个列表")
        self.assertEqual(len(results), 2, "应为每个derivation生成一个条目")

        # 验证第一个条目的结构和内容
        item1 = results[0]
        self.assertIn("question", item1)
        self.assertIn("ground_truth", item1)
        self.assertIn("blank_answer", item1)
        self.assertIn("hash", item1)
        
        self.assertEqual(item1["ground_truth"], "<derivation>A=B</derivation>")
        self.assertIn("[MASKED_DERIVATION]", item1["blank_answer"])
        self.assertNotIn("<derivation>A=B</derivation>", item1["blank_answer"])
        
        # 验证第二个条目的结构和内容
        item2 = results[1]
        self.assertEqual(item2["ground_truth"], "<derivation>C=D</derivation>")
        self.assertIn("[MASKED_DERIVATION]", item2["blank_answer"])
        self.assertNotIn("<derivation>C=D</derivation>", item2["blank_answer"])
        print("--- 测试通过 ---")

    def test_pipeline_data_flow_integration(self):
        """
        测试两个模块之间的数据流是否兼容。
        模块一的输出格式应能被模块二正确处理。
        """
        print("\n--- 正在运行测试: test_pipeline_data_flow_integration ---")
        
        # 模块一的模拟输出
        module1_output = self.module2_input_data # 使用预设的模拟数据
        
        # 将其作为模块二的输入
        module2_results = generate_fill_in_the_blanks(module1_output)
        
        # 断言模块二能成功处理并返回预期的结果数量
        self.assertTrue(len(module2_results) > 0, "模块二未能从模块一的输出中生成任何数据")
        self.assertEqual(len(module2_results), 2, "数据流整合测试失败，未生成预期数量的结果")
        
        print("--- 测试通过 ---")

# =======================================================================
# 主程序执行入口 (Main Execution Block)
# =======================================================================

if __name__ == "__main__":
    # --- 运行生产流程 ---
    # 说明:
    # 1. 首先，你需要准备一个名为 'storm-born.jsonl' 的输入文件。
    #    如果文件不存在，以下代码将创建一个示例文件。
    # 2. 其次，你需要配置 OpenAI API 客户端。
    #    请在下方代码中填入您的 API Key 和 Base URL。
    # 3. 取消下方 `run_pipeline()` 函数的注释即可运行完整的处理流程。
    
    def setup_example_input_file(filename='storm-born.jsonl'):
        """如果输入文件不存在，则创建一个示例文件。"""
        if not os.path.exists(filename):
            print(f"输入文件 '{filename}' 不存在，正在创建示例文件...")
            jsonl_data = {"paper":"arxiv:2305.18290", "question":"Given the formula, prove the optimal solution.", "whole_label":"To derive the optimal solution, we start by considering the optimization problem. <derivation>\\max_{\\pi}  \\mathbb{E}_{x\\sim \\mathcal{D}, y\\sim \\pi}\\bigl[r(x, y)\\bigr] - \\beta\\mathbb{D}_{\\textrm{KL}}\\bigl[\\pi(y|x)||\\pi_{\\text{ref}}(y|x)\\bigr].\\end{equation}</derivation> This can be rewritten as a minimization problem. <derivation>\\min_{\\pi}  \\mathbb{E}_{x\\sim \\mathcal{D}}\\mathbb{E}_{y\\sim \\pi(y|x)}\\left[\\log\\frac{\\pi(y|x)}{\\pi_{\\text{ref}}(y|x)} - \\frac{1}{\\beta}r(x, y)\\right].\\end{align}</derivation>"}
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json.dumps(jsonl_data) + '\n')
            print(f"示例输入文件 '{filename}' 已创建。")

    def run_pipeline():
        """执行完整的数据处理流水线。"""
        # --- 配置 ---
        # 警告：请不要将API密钥硬编码在代码中。建议使用环境变量。
        # from openai import OpenAI
        # client = OpenAI(
        #     api_key="在此处替换为您的API密钥",
        #     base_url="https://aihubmix.com/v1"
        # )
        
        # 由于我们无法访问外部API，此处的client将为None。
        # 在实际运行时，请务必取消上面代码的注释并提供有效的凭据。
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

        # 定义文件名
        input_filename = 'storm-born.jsonl'
        sub_label_output_filename = 'storm_born_divide_sublabel_output.jsonl'
        final_output_filename = 'fill_in_the_blanks_storm_born_data.jsonl'
        
        # 准备输入文件
        setup_example_input_file(input_filename)
        
        # 执行流程 - 现在使用实时处理模式
        divide_sublabel_module(input_filename, sub_label_output_filename, final_output_filename, client)
        
        print("流水线执行完毕！")

    # --- 运行单元测试 ---
    # 说明:
    # 取消下方代码的注释以运行单元测试。
    # 测试无需API密钥或真实文件即可运行。
    
    def run_tests():
        """执行单元测试套件。"""
        print("=========================================")
        print("          开始运行单元测试         ")
        print("=========================================")
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestDataProcessingPipeline))
        runner = unittest.TextTestRunner()
        runner.run(suite)

    # --- 选择要执行的操作 ---
    
    # 演示如何运行完整的生产流程 (当前已注释掉)
    print("--- 准备执行生产流程 ---")
    run_pipeline()

    print("\n")
    
    # # 演示如何运行单元测试
    # print("--- 准备执行单元测试 ---")
    # run_tests()