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



def extract_formula(model, sample_pdf, output_file):
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
    return latex_formulas
    formulas = "\n".join(latex_formulas)

def generate_query(model, latex_formulas:list, sample_pdf, output_file):
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
                continue
    with open(output_file, 'w', encoding='utf-8') as file:
        for item in query:
            file.write(item + '\n')
    print("the number of queries: "+str(len(query)))
    return query
    
def generate_label(model, query:list, sample_pdf, output_file:str):
    label=[]
    for i in range(0, len(query), 20):
        chunk = "\n".join(query[i:i+20])
        prompt3 = """我将提供一份从这篇论文中抽取得到的 JSONL 格式数据集。数据集中每条数据均为一个字典，包含两个主要键值对：  
1. **公式相关键（“formula”、“lemma”、“theorem”等）**，表示数学表达式的类别；值为从论文中提取出的 LaTeX 格式数学表达式；   
2. **query**，值为大模型根据论文与该数学表达式生成的问题。

请根据下列步骤与要求，对该数据集进行处理，不要遗漏数据。。

---

### 第一步：  
针对每条数据中的“表达式”与“query”，判断能否从论文中找到该问题的答案。具体步骤如下：  

1. **寻找首次出现的位置**  
   - 在论文中找到该表达式首次出现的位置，并查看该位置前后文寻找相关线索；  
   - 如果存在引用、参考，请继续跟进。

2. **检查附录和其他部分**  
   - 查询论文的附录或其他相关章节，查看是否提供了该表达式的证明过程或推导步骤，这很可能是问题答案。

3. **确认可行性**  
   - 若论文中确实存在可回答该问题的内容，则需提取原文中的相关内容，提取的答案内容需涵盖论文原文中解决问题所需的所有相关步骤和细节，不要概括、省略。在答案中仅保留原文内容（可作少量必要的衔接性编辑，但不改变原意），不要概括、省略，尽量避免额外添加未在原文出现的内容或描述。并且在答案最后表明答案的来源（evidence：答案在论文中的位置）。
   - 若论文中没有任何与问题相关的内容，认为问题答案为“NO ANSWER.”，并在最后标注“evidence: NO EVIDENCE”, 即提取的答案为“NO ANSWER.\nevidence: NO EVIDENCE”。 

在提取答案时，请注意以下要求：  
- **数目不变**：每条数据都对应一条答案，不可出现增添数据量。
- **完备性**：提取的答案内容需涵盖论文中解决问题所需的所有相关步骤和细节。  
- **一致性**：在答案中仅保留原文内容（可作少量必要的衔接性编辑，但不改变原意），尽量避免额外添加未在原文出现的内容或描述。
- **evidence**：在答案最后表明答案的来源（evidence：答案在论文中的位置）。
- **引用处理**：若答案中引用了论文中的其它公式、定理，请同时将其原始内容包含在推导或证明过程中，而不仅仅保留编号或标签。  
- **LaTeX 转换**：请确保所有数学表达式均转为与原文一致的 LaTeX 格式，包括：  
  - 符号、上下标及大小写的准确性；  
  - 保留表达式原有结构及编号（若有）；  
  - 斜体变量使用 `\textit{}`；  
  - 行内数学表达式使用 `$...$`，行间使用 `$$...$$`。

---

### 第二步：  
**JSONL 输出：** 将第一步中提取的答案以多行 JSONL 格式输出，方便逐行解析。每行都是一个 JSON 对象，原来的内容保持不变，不可以增补、删除、修改；另外新增一个键值对，其中 key 为`whole_label`，value 为第一步中从论文中提取的 LaTeX 格式的答案内容，并且需要在答案最后表明答案的来源（evidence：答案所在位置）；

---

### 输出要求：
1. **多行 JSONL 格式**：每条数据一行。  
2. **内容准确性**：公式须与论文原文完全一致，所有符号、上下标与大小写的转换必须正确。 
3. **内容一致性**：在答案中仅保留原文内容（可作少量必要的衔接性编辑，但不改变原意），尽量避免额外添加未在原文出现的内容或描述。
4. **evidence**：在答案最后表明答案的来源（evidence：答案在论文中的位置）。

---

### 注意：
- 输出数据和输入数据一一对应，不可多余或缺少。
- 请严格遵照以上要求，避免缺少任何关键内容。  
- 确保输出文本中无错误或不完整之处。  
- 提取的答案内容需涵盖论文中解决问题所需的所有相关步骤和细节。
- 在输出答案中仅保留原文内容（可作少量必要的衔接性编辑，但不改变原意），尽量避免额外添加未在原文出现的内容或描述。
- 在答案最后表明答案的来源（evidence：答案在论文中的位置）。

---

数据集如下："""  + chunk#- 仅对能够找到答案且答案属于“证明过程”或“公式推导过程”的记录进行此处理；若未找到答案，或答案并非证明/推导过程，则不输出。
        prompt3 = """\nI will provide a JSONL-format dataset extracted from this paper. Each piece of data in the dataset is a dictionary containing two main key-value pairs:
1. **Formula-related keys ("formula", "lemma", "theorem", etc.)** indicating the type of mathematical expression; the value is the LaTeX-formatted mathematical expression extracted from the paper.
2. **query**, whose value is a question generated by a large model based on the paper and the mathematical expression.

Please process this dataset according to the following steps and requirements.

---

### Step One:
For the “expression” and “query” in each piece of data, determine whether the answer to that question can be found in the paper. The specific steps are as follows:

1. **Find the first occurrence**
   - Locate where the expression first appears in the paper and check the surrounding context for relevant clues.
   - If there are any references or citations, follow those as well.

2. **Check the appendix and other sections**
   - Search the paper’s appendix or other relevant chapters to see if the proof or derivation steps for that expression are provided. This may well be the answer to the question.

3. **Confirm feasibility**
   - If the paper does not include any relevant content addressing the question, you may skip this expression and proceed to the next one.
   - If the paper does indeed contain content that can answer the question, extract the relevant content from the original text.

When extracting the answer, please note the following requirements:
- **Completeness**: The extracted answers should cover all the relevant steps needed to solve the problem in the paper.
- **Consistency**: Include only content from the original text in the answer (you may make minimal necessary edits for coherence, but do not change the original meaning). Avoid adding extra content or descriptions not found in the original text.
- **Citation handling**: If the answer cites other formulas or theorems from the paper, also include their original content in the derivation or proof process, rather than leaving only references or labels.
- **LaTeX conversion**: Ensure all mathematical expressions are converted to the same LaTeX format as in the original text, including:
  - Accuracy of symbols, subscripts, superscripts, and capitalization.
  - Preserving the original structure and numbering (if any).
  - Using \textit{} for italicized variables.
  - Using $...$ for inline math expressions and $$...$$ for display math expressions.

---

### Step Two:
Match the answers extracted in Step One with the corresponding entries in the dataset, and add a new key-value pair to form a new data record. The specific requirements are:

- For each original data entry, add a new key called `whole_label`, whose value is the LaTeX-formatted answer content extracted from the paper.
- Output format must be **multi-line JSONL**, one piece of data per line:
  1. The original two key-value pairs remain unchanged and must not be modified.
  2. Add the `whole_label` key as the third key-value pair.

---

### Output Requirements:
1. **Multi-line JSONL format**: One data entry per line.
2. **Accuracy of content**: Formulas must match the original text of the paper exactly, with correct symbols, subscripts, superscripts, and capitalization.
3. ** Content consistency ** : Only retain the original content in the answer (you can make a small amount of necessary cohesive editing, but do not change the original meaning), and try to avoid adding additional content or descriptions that do not appear in the original.
---

### Note:
- Please strictly follow the above requirements to avoid omitting any key content.
- Ensure there are no errors or incomplete parts in the output text.

---

Below is the dataset:
""" + chunk
        response3 = model.generate_content([sample_pdf, prompt3], generation_config=genai.types.GenerationConfig(temperature=0.0,),request_options={"timeout": 600})
        for line in response3.text.splitlines():
            try:
                json_obj = json.loads(line)
                if not line in label:
                    label.append(line)
            except json.JSONDecodeError as e:
                continue
    with open(output_file, 'w', encoding='utf-8') as file:
        for item in label:
            file.write(item + '\n')
    print("the number of label_answers: "+str(len(label)))
    return label

if __name__ == '__main__':
# class Recipe(typing.TypedDict):
#     recipe_name: str
#     ingredients: list[str]
    start = time.time()
    # output_dir = "E:\\dmt\\formula\\generated\\1-8"
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_path', type=str, default="E:\dmt\\formula\\Direct Preference Optimization--Your Language Model is Secretly a Reward Mode.pdf", help='the input file path')
    parser.add_argument('--model_name', type=str, default="gemini-2.0-flash-exp", help='the gemini model you want to use.')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated", help='output dir')
    args = parser.parse_args()
    # args.output_jsonl_path = os.path.join(output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_label.jsonl")
    print("pdf: " + args.pdf_path)
    print("model: " + args.model_name)
    print("output_dir: " + args.output_dir)

    genai.configure(api_key="AIzaSyC3hUut2AKGPAsRE7MN-s0LecjOEdg2bcg")
    model = genai.GenerativeModel(args.model_name)
    # model3 = genai.GenerativeModel("gemini-2.0-flash-thinking-exp")
    sample_pdf = genai.upload_file(args.pdf_path)
    prepare = time.time()
    formula_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_formula.jsonl")
    print(formula_path)
    formulas = extract_formula(model, sample_pdf, formula_path)
    formulas_time = time.time()
    # qa = generate_question_label(formulas, args.output_jsonl_path, sample_pdf)
    query_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_query.jsonl")
    query = generate_query(model, formulas, sample_pdf, query_path)
    query_time = time.time()
    QA_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_QA.jsonl")
    label = generate_label(model, query, sample_pdf, QA_path)
    label_time = time.time()
    print(f"Time to configure model and upload file: {prepare - start:.2f} seconds")
    print(f"Time to extract formulas: {formulas_time - prepare:.2f} seconds")
    print(f"Time to generate queries: {query_time - formulas_time:.2f} seconds")
    print(f"Time to generate labels: {label_time - query_time:.2f} seconds")
    print(f"Total time elapsed: {label_time - start:.2f} seconds")
