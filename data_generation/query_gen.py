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

def generate_query(model_name, latex_formulas:list, pdf_path, output_dir):
    model = genai.GenerativeModel(model_name)
    sample_pdf = genai.upload_file(pdf_path)
    output_file = os.path.join(output_dir, "api_"+ pdf_path.split('\\')[-1][:-4]+"_query.jsonl")

    query=[]
    for i in range(0, len(latex_formulas), 20):
        chunk = "\n".join(latex_formulas[i:i+20])
        prompt2 = """我会给你一个从这篇论文中抽取得到的数据集，为jsonl格式，每一条数据为一个dict数据，key为“formula”、“lemma”、“theorem”等，代表数学表达式的类别，value是从论文中抽取的一个数学表达式的内容，为latex格式。
        
仔细阅读和理解论文内容，特别是与 JSONL 中每个公式相关的部分。
对其中每一条公式，请按以下步骤完成任务：

### 第一步：
从论文中找到该公式**首次定义或首次完整推导**的位置，并结合上下文提取**推导或证明该公式的所有直接必要条件**。前提条件包括但不限于以下内容：
1.  **该公式从哪些其他公式推导而来，或依赖哪些其他公式。对于这些公式，请记录它们的完整内容（使用 LaTeX 格式）、序号（如果有的话）和名称（如果有的话）。**
2.  相关问题设定。
3.  公式中涉及的符号或变量的具体含义。

### 第二步：
基于提取的前提条件，生成一个完整的问题，明确询问如何推导或证明该公式。问题内容应包括：
1.  **当前公式本身**：完整展示该公式内容（使用 LaTeX 格式），不要仅引用序号。
2.  **前提条件**：将论文中提取的前提条件**明确地整合到问题中，并详细列出所有依赖的公式的完整内容，并使用它们的序号或名称进行引用**。不要生成类似“前提条件是什么”的问题。

问题的形式需符合以下要求：
-   如果一个公式是由**另一个或多个公式**推导而来的，请**明确列出这些公式的完整内容（使用 LaTeX 格式），并使用它们的序号或名称进行引用**，并说明是如何从这些公式推导得出当前公式。 例如：假设论文中有公式3 (内容是 X)和公式4 (内容是 Y)，其中公式4是由公式3推导得出的，那么生成的问题应该是：
    “**根据公式3： X，如何推导出公式4： Y ？**”
-   如果公式是一个定理、引理或推论，请生成问题询问如何证明，例如：
    “如何证明 Lemma 1：X 成立？”

请注意：**问题需要有条理有逻辑，清晰地表达公式的推导或证明过程，并明确体现公式间的依赖关系，同时完整展示所有相关公式的内容。**

### 第三步：
将生成的问题与对应的公式一一匹配，并以多行的 JSONL 格式输出。

每条数据应为一个字典，包含以下两对键值：
1.  **公式类型**：
    -   Key 为 formula、lemma、theorem 等，
    -   Value 为公式的 LaTeX 格式内容。
2.  **生成的问题**：
    -   Key 为 query，
    -   Value 为根据第一步和第二步生成的完整问题内容。

### 注意事项：
1.  **格式要求**：
    -   确保输出为 JSONL 格式，每行对应一条数据。
2.  **公式准确性**：
    -   若问题中包含数学表达式，请将其转换为 LaTeX 格式，保证公式与原文**数学含义**一致，可以适当忽略格式上的差异。
3.  **LaTeX 转换：** 将问题中包含的数学表达式转换为 LaTeX 格式的字符串。
        *   **符号:** 准确转换数学符号。
        *   **上下标:** 正确识别和转换上下标。
        *   **大小写:** 保持变量和常量的大小写一致。
        *   **公式结构:** 保持公式的完整结构。
        *   **公式编号:** 保留公式的编号（如果有的话）。
        *   **斜体:** 文本中斜体的变量，用 LaTeX 的 `\\textit{}` 包裹。
        *   **数学环境:** 行内公式使用 `$ ... $` 包裹，行间公式使用 `$$ ... $$` 包裹。
4.  **前提条件完整性**：
    -   问题内容中应包含提取的**所有直接必要条件**，**尤其是该公式从哪些其他公式推导而来，或依赖哪些其他公式，并明确指出这些公式的完整内容、序号或名称，在生成的问题中，把引用公式的原始的完整内容也展示出来，写在引用序号后。**。不允许生成类似“前提条件是什么”的问题。

### 示例：
以下是一些示例问题及其对应的输出格式，供参考：
假设论文中包含以下公式：
{"lemma": "Lemma 1.  The function $f(x)$ is continuous."}
那么，生成的问题可能是：
{"query":"如何证明 Lemma 1： The function $f(x)$ is continuous. 成立？"}

假设论文中包含以下公式：
{"formula": "y = mx + b"}
并且论文说明该公式是由 y = f(x) 和 f(x) = mx + b 推导而来，那么，生成的问题可能是：
{"query":"根据公式：$y = f(x)$ 和 $f(x) = mx + b$，如何推导出公式：$y = mx + b$ ？"}

假设论文中包含以下公式：
{"formula": "$$\\pi_r(y | x) = \\frac{1}{Z(x)} \\pi_{ref}(y | x) \\exp (\\frac{1}{\\beta} r(x, y))$$"}
并且论文说明该公式是由公式3 $KL(\\pi_r(y|x) || \\pi_{ref}(y|x)) \\leq \\epsilon$ 推导而来，那么，生成的问题应该是：
{"query":"根据公式3：$KL(\\pi_r(y|x) || \\pi_{ref}(y|x)) \\leq \\epsilon$，如何推导出公式：$\\pi_r(y | x) = \\frac{1}{Z(x)} \\pi_{ref}(y | x) \\exp (\\frac{1}{\\beta} r(x, y))$ ？"}

数据集如下：\n""" + chunk#query
        prompt2 = """I will provide you with a dataset extracted from this paper, in JSONL format. Each entry is a dictionary whose keys are “formula,” “lemma,” “theorem,” etc., representing the category of the mathematical expression, and whose values contain a mathematical expression in LaTeX format, extracted from the paper.

Carefully read and understand the paper’s content, especially the parts related to each formula in the JSONL. For each formula, please complete the following steps:

---

Step 1:
Locate where the formula is first defined or fully derived in the paper, and use the relevant context to extract all the direct necessary conditions for deriving or proving that formula. These preconditions include, but are not limited to:

1. Which other formulas this formula is derived from or depends on. For each such formula, record its full content (in LaTeX format), its numbering (if any), and its name (if any).
2. Relevant problem settings.
3. The specific meaning of symbols or variables involved in the formula.

---

Step 2:
Based on the extracted preconditions, generate a complete question that clearly asks how to derive or prove the formula. The question should include:

1. The formula itself: Present the full content of this formula (in LaTeX format). Do not only reference its number.
2. The preconditions: Explicitly integrate the preconditions extracted from the paper into the question. List out the full contents of all the formulas it depends on and reference them by their respective numbers or names. Do not produce a question such as “What are the preconditions?”

The form of the question must meet the following requirements:

- If a formula is derived from one or more other formulas, you must explicitly list the full content (in LaTeX) of these preceding formulas and reference them by their numbers or names, and explain how the current formula is derived from them. For example, if the paper contains Formula 3 (content: X) and Formula 4 (content: Y), and Formula 4 is derived from Formula 3, then the generated question should be:

“Based on Formula 3: X, how can we derive Formula 4: Y?”

- If the formula is a theorem, lemma, or corollary, please generate a question asking how to prove it, for example:

“How can we prove Lemma 1: X is true?”

Note: The question must be structured and logical, clearly showing the derivation or proof process of the formula and explicitly reflecting the dependency between formulas while fully presenting all related formulas.

---

Step 3:
Match each formula with its corresponding question and output the result in multi-line JSONL format.

Each data entry should be a dictionary containing the following two key-value pairs:

1. Formula type:
- The key is “formula,” “lemma,” “theorem,” etc.
- The value is the LaTeX content of the formula.
2. Generated question:
- The key is “query.”
- The value is the complete question generated according to Step 1 and Step 2.

---

Important Notes:
1. Format Requirements:
- Ensure the output is in JSONL format, with each line corresponding to one data entry.
2. Formula Accuracy:
- If the question contains mathematical expressions, convert them into LaTeX format. Make sure they align with the original mathematical meaning. Minor formatting differences can be ignored.
3. LaTeX Conversion(Converts the mathematical expressions contained in the problem to strings in LaTeX format):
- Symbols: Convert mathematical symbols accurately.
- Subscripts and superscripts: Convert subscripts and superscripts correctly.
- Uppercase and lowercase: Preserve the original variable and constant casing.
- Formula structure: Keep the entire structure of the formula intact.
- Formula numbering: Retain the formula’s number (if any).
- Italics: For italicized variables in the text, wrap them with \textit{} in LaTeX.
- Math environment: Use `$ ... $` for inline formulas and `$$ ... $$` for block (display) formulas.
4. Completeness of Preconditions:
- The question content must include all direct necessary conditions. Particularly, indicate which other formulas the current formula is derived from or depends on, and clearly specify the entire content, numbering, or name of those referenced formulas. Do not produce questions such as “What are the preconditions?”

---

Examples:
Here are some example questions and their corresponding output formats for reference:

- Suppose the paper contains the following formula:
{"lemma": "Lemma 1.  The function $f(x)$ is continuous."}
The generated question might be:
{"query":"How can we prove Lemma 1: The function $f(x)$ is continuous. is true?"}

- Suppose the paper contains the following formula:
{"formula": "y = mx + b"}
and it is explained that this formula is derived from y = f(x) and f(x) = mx + b. Then the generated question might be:
{"query":"Based on the formulas: $y = f(x)$ and $f(x) = mx + b$, how can we derive the formula: $y = mx + b$?"}

- Suppose the paper contains the following formula:
{"formula": "$$\\pi_r(y | x) = \\frac{1}{Z(x)} \\pi_{ref}(y | x) \\exp (\\frac{1}{\\beta} r(x, y))$$"}
and it is explained that this formula is derived from Formula 3, $KL(\\pi_r(y|x) || \\pi_{ref}(y|x)) \\leq \\epsilon$. Then the generated question should be:
{"query":"Based on Formula 3: $KL(\\pi_r(y|x) || \\pi_{ref}(y|x)) \\leq \\epsilon$, how can we derive Formula: $\\pi_r(y | x) = \\frac{1}{Z(x)} \\pi_{ref}(y | x) \\exp (\\frac{1}{\\beta} r(x, y))$?"}

The dataset is as follows:\n""" + chunk# Notes:Ensure the output is in JSONL format! If the generated questions include mathematical formulas, convert them into LaTeX format. Ensure the formulas are consistent with the original text, including the correct symbols, subscripts, superscripts, and case sensitivity.
        response2 = model.generate_content([sample_pdf, prompt2], generation_config=genai.types.GenerationConfig(temperature=0.0,),request_options={"timeout": 600})
        for line in response2.text.splitlines():
            try:
                json_obj = json.loads(line)
                if not line in query:
                    query.append(line)
            except json.JSONDecodeError as e:
                print(line)
                continue
    with open(output_file, 'w', encoding='utf-8') as file:
        for item in query:
            file.write(item + '\n')
    print("the number of queries: "+str(len(query)))
    return query, output_file
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_path', type=str, default="E:\dmt\\formula\\Direct Preference Optimization--Your Language Model is Secretly a Reward Mode.pdf", help='the input file path')
    parser.add_argument('--model_name', type=str, default="gemini-2.0-flash-exp", help='the gemini model you want to use.')
    parser.add_argument('--input_path', type=str, default="E:\dmt\\formula\\generated\\final_test\\api_Direct Preference Optimization--Your Language Model is Secretly a Reward Mode_formula.jsonl", help='input math expressions(.jsonl)')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated\\final_test", help='output dir')
    args = parser.parse_args()
    print("pdf: " + args.pdf_path)
    print("model: " + args.model_name)
    print("input math expressions(.jsonl): " + args.input_path)
    print("output_dir: " + args.output_dir)


    formulas = []
    with open(args.input_path, 'r', encoding='utf-8') as infile:
        for line in infile:
            # formulas.append(line)
            data = json.loads(line.strip())
            formulas.append(data)
            # print(formulas)
            # assert  0

    query_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_query.jsonl")
    query, outputfile = generate_query(args.model_name, formulas, args.pdf_path, args.output_dir)
    
