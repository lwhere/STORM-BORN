import json
import openai
import time
import re
from typing import List, Dict, Any

client = openai.OpenAI(
  api_key="sk-xxxxxxx",
    base_url="https://aihubmix.com/v1"  
)

def read_jsonl(file_path: str) -> List[Dict[str, Any]]:
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def write_jsonl(data: List[Dict[str, Any]], file_path: str):
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            json.dump(item, f, ensure_ascii=False)
            f.write('\n')

def append_to_jsonl(item: Dict[str, Any], file_path: str):
    with open(file_path, 'a', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False)
        f.write('\n')

def apply_mask_optimization(sub_label: str, target_equation: str) -> str:
    target_equation_clean = target_equation.replace("<equation>", "").replace("</equation>", "").strip()
    full_equation_tag = f"<equation>{target_equation_clean}</equation>"
    
    optimized_sub_label = sub_label.replace(full_equation_tag, "[Missing Equation]", 1)
    return optimized_sub_label

def generate_missing_equation(question: str, blank_answer: str) -> str:
    
    prompt = f"""You are a mathematical assistant. Given a mathematical question and a partially completed derivation with a missing equation, you need to fill in the missing equation.

Question: {question}

Partial derivation with missing equation:
{blank_answer}

Please provide ONLY the missing equation in LaTeX format, without any explanation or additional text. The equation should be the mathematical formula that fits logically in the [Missing Equation] position.

Your response should be just the LaTeX equation, nothing else."""

    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash-lite",  # 根据你的模型调整
            messages=[
                {"role": "system", "content": "You are a mathematical assistant that provides precise LaTeX equations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating equation: {e}")
        return ""

def check_equivalence(generated_eq: str, ground_truth: str) -> Dict[str, Any]:
    
    ground_truth_clean = ground_truth.replace("<equation>", "").replace("</equation>", "").strip()
    
    prompt = f"""You are a mathematical expert. Your task is to determine if two mathematical equations are mathematically equivalent.

Equation 1: {generated_eq}
Equation 2: {ground_truth_clean}

Consider the following:
1. Mathematical equivalence (same meaning, different notation is OK)
2. Variable names can be different but should represent the same concepts
3. Order of terms can be different
4. Equivalent forms of the same equation

Respond with ONLY:
- "EQUIVALENT" if the equations are mathematically equivalent
- "NOT_EQUIVALENT" if they are not equivalent
- "UNCLEAR" if you cannot determine

No explanation needed, just the classification."""

    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash-lite",  # 根据你的模型调整
            messages=[
                {"role": "system", "content": "You are a mathematical expert that determines equation equivalence."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=50
        )
        
        result = response.choices[0].message.content.strip().upper()
        
        # 解析结果
        if "EQUIVALENT" in result:
            return {"equivalent": True, "reason": "LLM判断为等价"}
        elif "NOT_EQUIVALENT" in result:
            return {"equivalent": False, "reason": "LLM判断为不等价"}
        else:
            return {"equivalent": None, "reason": "LLM无法判断"}
            
    except Exception as e:
        print(f"Error checking equivalence: {e}")
        return {"equivalent": None, "reason": f"检查等价性时出错: {e}"}

def process_single_item_with_optimization(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    print(f"\n处理第 {index + 1} 题...")
    
    question = item["question"]
    blank_answer = item["blank_answer"]
    ground_truth = item["ground_truth"]
    
    print("正在生成missing equation...")
    generated_equation = generate_missing_equation(question, blank_answer)
    
    if not generated_equation:
        print("生成方程失败，跳过此题")
        return None
    
    print(f"生成的方程: {generated_equation}")
    
    print("正在检查等价性...")
    equivalence_result = check_equivalence(generated_equation, ground_truth)
    
    print("正在进行mask优化...")
    original_sub_label = blank_answer.replace("[Missing Equation]", ground_truth)
    
    optimized_blank_answer = apply_mask_optimization(original_sub_label, ground_truth)
    
    result = {
        "question_id": index + 1,
        "question": question,
        "original_blank_answer": blank_answer,
        "optimized_blank_answer": optimized_blank_answer,
        "ground_truth": ground_truth,
        "generated_equation": generated_equation,
        "equivalence_result": equivalence_result,
        "original_sub_label": original_sub_label
    }
    
    # 统计
    if equivalence_result["equivalent"]:
        print("正确")
    elif equivalence_result["equivalent"] is False:
        print("错误")
    else:
        print("无法判断")
    
    return result

def evaluate_fill_blanks_with_realtime_optimization():
    
    data = read_jsonl("fill_in_the_blanks_data.jsonl")
    print(f"读取到 {len(data)} 条填空题数据")
    
    results = []
    correct_count = 0
    total_count = 0
    
    evaluation_output_file = "evaluation_with_optimization.jsonl"
    optimized_data_file = "optimized_data_realtime.jsonl"
    
    with open(evaluation_output_file, 'w', encoding='utf-8') as f:
        pass
    with open(optimized_data_file, 'w', encoding='utf-8') as f:
        pass
    
    for i, item in enumerate(data):
        result = process_single_item_with_optimization(item, i)
        
        if result is None:
            continue
        
        results.append(result)
        total_count += 1
        
        if result["equivalence_result"]["equivalent"]:
            correct_count += 1
        
        append_to_jsonl(result, evaluation_output_file)
        print(f"已实时保存评估结果到 {evaluation_output_file}")
        
        optimized_item = {
            "question": result["question"],
            "ground_truth": result["ground_truth"],
            "blank_answer": result["optimized_blank_answer"],
            "hash": item.get("hash", "")
        }
        append_to_jsonl(optimized_item, optimized_data_file)
        print(f"已实时保存优化数据到 {optimized_data_file}")
        
        time.sleep(1)
    
    print(f"\n=== 评估结果 ===")
    print(f"总题数: {total_count}")
    print(f"正确数: {correct_count}")
    print(f"准确率: {correct_count/total_count*100:.2f}%" if total_count > 0 else "准确率: 0%")
    
    with open("evaluation_results_detailed.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": total_count,
                "correct": correct_count,
                "accuracy": correct_count/total_count*100 if total_count > 0 else 0
            },
            "detailed_results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到 evaluation_results_detailed.json")
    print(f"实时评估结果已保存到 {evaluation_output_file}")
    print(f"实时优化数据已保存到 {optimized_data_file}")

def process_single_item(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    print(f"\n处理第 {index + 1} 题...")
    
    question = item["question"]
    blank_answer = item["blank_answer"]
    ground_truth = item["ground_truth"]
    
    print("正在生成missing equation...")
    generated_equation = generate_missing_equation(question, blank_answer)
    
    if not generated_equation:
        print("生成方程失败，跳过此题")
        return None
    
    print(f"生成的方程: {generated_equation}")
    
    print("正在检查等价性...")
    equivalence_result = check_equivalence(generated_equation, ground_truth)
    
    result = {
        "question_id": index + 1,
        "question": question,
        "blank_answer": blank_answer,
        "ground_truth": ground_truth,
        "generated_equation": generated_equation,
        "equivalence_result": equivalence_result
    }
    
    if equivalence_result["equivalent"]:
        print("✓ 正确")
    elif equivalence_result["equivalent"] is False:
        print("✗ 错误")
    else:
        print("? 无法判断")
    
    return result

def evaluate_fill_blanks():

    data = read_jsonl("fill_in_the_blanks_data.jsonl")
    print(f"读取到 {len(data)} 条填空题数据")
    
    results = []
    correct_count = 0
    total_count = 0
    
    sub_label_output_file = "sub_label_output.jsonl"
    processed_results = []
    
    for i, item in enumerate(data):
        result = process_single_item(item, i)
        
        if result is None:
            continue
        
        results.append(result)
        total_count += 1
        
        if result["equivalence_result"]["equivalent"]:
            correct_count += 1
        
        processed_results.append(result)
        write_jsonl(processed_results, sub_label_output_file)
        print(f"已实时保存到 {sub_label_output_file}")
        
        time.sleep(1)
    
    print(f"\n=== 评估结果 ===")
    print(f"总题数: {total_count}")
    print(f"正确数: {correct_count}")
    print(f"准确率: {correct_count/total_count*100:.2f}%" if total_count > 0 else "准确率: 0%")
    
    with open("evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": total_count,
                "correct": correct_count,
                "accuracy": correct_count/total_count*100 if total_count > 0 else 0
            },
            "detailed_results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到 evaluation_results.json")
    print(f"实时处理结果已保存到 {sub_label_output_file}")

if __name__ == "__main__":
    # 选择运行模式
    print("请选择运行模式:")
    print("1. 原始评估模式（不包含实时优化）")
    print("2. 实时优化评估模式（推荐）")
    
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == "1":
        evaluate_fill_blanks()
    elif choice == "2":
        evaluate_fill_blanks_with_realtime_optimization()
    else:
        print("无效选择，运行实时优化评估模式")
        evaluate_fill_blanks_with_realtime_optimization() 
