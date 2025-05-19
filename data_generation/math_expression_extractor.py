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


genai.configure(api_key="AIzaSyC3hUut2AKGPAsRE7MN-s0LecjOEdg2bcg")

def extract_formula(model_name, pdf_path, output_dir):
    model = genai.GenerativeModel(model_name)
    sample_pdf = genai.upload_file(pdf_path)
    output_file = os.path.join(output_dir, "api_"+ pdf_path.split('\\')[-1][:-4]+"_formula.jsonl")

    prompt1 = """阅读这篇论文，然后：

1.  **公式识别：** 
    *   找出论文中出现的所有数学公式、定理、引理和推论。保留公式的编号。
    *   对于没有明确类型标识的公式（即没有 "定理"、"引理"、"推论" 等关键词），统一归类为 "formula"。
    *   **需要识别以下类型的公式：**
        *   **带有编号的公式：**  保留公式的编号。
        *   **单独成行的公式：**  例如，在论文中单独占据一行或多行的公式。保留公式的编号（如果存在编号）。
    *   **忽略以下类型的公式：**
        *   **在段落中间出现的而且没有单独成行、也没有编号的公式。**
    *   确保结果中不包含重复的公式（重复指 LaTeX 转换后完全相同的公式。若同一内容在论文中以不同编号出现，视为相同公式）。

2.  **LaTeX 转换：** 将第一步中找到的公式转换为 LaTeX 格式的字符串。
    *   **公式编号:** 保留公式的编号（如果存在）。
    *   **Formula numbering:** Retain the formula’s number (if any)。
    *   **符号:** 准确转换数学符号。
    *   **上下标:** 正确识别和转换上下标。
    *   **大小写:** 保持变量和常量的大小写一致。
    *   **公式结构:** 保持公式的完整结构。
    *   **斜体:** 文本中斜体的变量，用 LaTeX 的 `\\textit{}` 包裹。
    *   **数学环境:** 行内公式使用 `$ ... $` 包裹，行间公式使用 `$$ ... $$` 包裹。
    *   **补充条件:** 查看紧跟在公式后面的论文内容是不是有对公式出现的符号的定义或说明，比如"where X is ..."。

3.  **JSONL 输出：** 将所有转换后的 LaTeX 格式字符串以多行 JSONL 格式输出，方便逐行解析。每行都是一个 JSON 对象，其中 key 为公式的类型（如 "formula", "lemma", "theorem", "corollary" 等），value 为对应的 LaTeX 转换得到的字符串，注意按照第2步的要求！

保留公式的编号（如果存在）。
确保公式和原文完全一致！"""
    prompt1 = """Read the paper, then:

1. Formula Recognition:
- Identify all mathematical formulas, theorems, lemmas, and corollaries in the paper. Especially Numbered formulas.Retain the formula’s number (if any).
- For formulas without explicit labels (i.e., those not labeled as "theorem," "lemma," or "corollary"), classify them as "formula."
- Required types of formulas to recognize:
    - Numbered formulas.
    - Formulas that appear on separate lines (for example, occupying a line or multiple lines by themselves in the paper).
- Ignore:
    - Formulas that appear in the middle of a paragraph without separate lines or numbers.
- Make sure there are no duplicates in the results (duplicates refer to formulas that are exactly the same after conversion to LaTeX. If the same formula appears in the paper under different numbers, treat them as the same formula).

2. LaTeX Conversion(Convert the formulas identified in step 1 into LaTeX format strings):
- Symbols: Convert mathematical symbols accurately.
- Subscripts and superscripts: Convert subscripts and superscripts correctly.
- Uppercase and lowercase: Preserve the original variable and constant casing.
- Formula structure: Keep the entire structure of the formula intact.
- Formula numbering: Retain the formula’s number (if any).
- Italics: For italicized variables in the text, wrap them with \textit{} in LaTeX.
- Math environment: Use `$ ... $` for inline formulas and `$$ ... $$` for block (display) formulas.
- Additional conditions: Check whether the paper includes definitions or explanations immediately following the formula (for example, “where X is ...”) and incorporate them if present.

3. JSONL Output:
- Output all converted LaTeX strings in multi-line JSONL format so they can be parsed line by line.
- Each line should be a JSON object whose key is the type of the formula ("formula", "lemma", "theorem", "corollary", etc.) and whose value is the LaTeX string obtained from step 2.
- Be sure to follow the requirements in step 2!

Ensure the formulas are exactly the same as in the original text!"""
    response1 = model.generate_content([sample_pdf,prompt1], generation_config=genai.types.GenerationConfig(temperature=0.0,), request_options={"timeout": 600})
    latex_formulas = []
    for line in response1.text.splitlines():
        try:
            json_obj = json.loads(line)
            # print(type(response1.text),type(line),line,json_obj['formula'],sep="\n")
            # assert 0 
            if not line in latex_formulas:
                latex_formulas.append(line)
                # print(line)
        except json.JSONDecodeError as e:
            continue
    print("the number of formulas/theorems: "+str(len(latex_formulas)))
    with open(output_file, 'w', encoding='utf-8') as file:
        for item in latex_formulas:
            file.write(item + '\n')
    # assert 0
    # assert 0
    return latex_formulas, output_file
    formulas = "\n".join(latex_formulas)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_path', type=str, default="E:\dmt\\formula\\Direct Preference Optimization--Your Language Model is Secretly a Reward Mode.pdf", help='the input file path')
    parser.add_argument('--model_name', type=str, default="gemini-2.0-flash-exp", help='the gemini model you want to use.')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated\\final_test", help='output dir')
    args = parser.parse_args()
    print("pdf: " + args.pdf_path)
    print("model: " + args.model_name)
    print("output_dir: " + args.output_dir)
    formulas, output_file = extract_formula(args.model_name, args.pdf_path, args.output_dir)
    print("ok")