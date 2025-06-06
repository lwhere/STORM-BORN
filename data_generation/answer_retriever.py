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

def generate_label(model_name, query:list, pdf_path, output_dir):
    model = genai.GenerativeModel(model_name)
    sample_pdf = genai.upload_file(pdf_path)
    output_file = os.path.join(output_dir, "api_"+ pdf_path.split('\\')[-1][:-4]+"_QA.jsonl")

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
#         prompt3 = """\nI will provide a JSONL-format dataset extracted from this paper. Each piece of data in the dataset is a dictionary containing two main key-value pairs:
# 1. **Formula-related keys ("formula", "lemma", "theorem", etc.)** indicating the type of mathematical expression; the value is the LaTeX-formatted mathematical expression extracted from the paper.
# 2. **query**, whose value is a question generated by a large model based on the paper and the mathematical expression.

# Please process this dataset according to the following steps and requirements.

# ---

# ### Step One:
# For the “expression” and “query” in each piece of data, determine whether the answer to that question can be found in the paper. The specific steps are as follows:

# 1. **Find the first occurrence**
#    - Locate where the expression first appears in the paper and check the surrounding context for relevant clues.
#    - If there are any references or citations, follow those as well.

# 2. **Check the appendix and other sections**
#    - Search the paper’s appendix or other relevant chapters to see if the proof or derivation steps for that expression are provided. This may well be the answer to the question.

# 3. **Confirm feasibility**
#    - If the paper does not include any relevant content addressing the question, you may skip this expression and proceed to the next one.
#    - If the paper does indeed contain content that can answer the question, extract the relevant content from the original text.

# When extracting the answer, please note the following requirements:
# - **Completeness**: The extracted answers should cover all the relevant steps needed to solve the problem in the paper.
# - **Consistency**: Include only content from the original text in the answer (you may make minimal necessary edits for coherence, but do not change the original meaning). Avoid adding extra content or descriptions not found in the original text.
# - **Citation handling**: If the answer cites other formulas or theorems from the paper, also include their original content in the derivation or proof process, rather than leaving only references or labels.
# - **LaTeX conversion**: Ensure all mathematical expressions are converted to the same LaTeX format as in the original text, including:
#   - Accuracy of symbols, subscripts, superscripts, and capitalization.
#   - Preserving the original structure and numbering (if any).
#   - Using \textit{} for italicized variables.
#   - Using $...$ for inline math expressions and $$...$$ for display math expressions.

# ---

# ### Step Two:
# Match the answers extracted in Step One with the corresponding entries in the dataset, and add a new key-value pair to form a new data record. The specific requirements are:

# - For each original data entry, add a new key called `whole_label`, whose value is the LaTeX-formatted answer content extracted from the paper.
# - Output format must be **multi-line JSONL**, one piece of data per line:
#   1. The original two key-value pairs remain unchanged and must not be modified.
#   2. Add the `whole_label` key as the third key-value pair.

# ---

# ### Output Requirements:
# 1. **Multi-line JSONL format**: One data entry per line.
# 2. **Accuracy of content**: Formulas must match the original text of the paper exactly, with correct symbols, subscripts, superscripts, and capitalization.
# 3. ** Content consistency ** : Only retain the original content in the answer (you can make a small amount of necessary cohesive editing, but do not change the original meaning), and try to avoid adding additional content or descriptions that do not appear in the original.
# ---

# ### Note:
# - Please strictly follow the above requirements to avoid omitting any key content.
# - Ensure there are no errors or incomplete parts in the output text.

# ---

# Below is the dataset:
# """ + chunk
        response3 = model.generate_content([sample_pdf, prompt3], generation_config=genai.types.GenerationConfig(temperature=0.0,),request_options={"timeout": 600})
        for line in response3.text.splitlines():
            try:
                json_obj = json.loads(line)
                if not line in label:
                    label.append(line)
            except json.JSONDecodeError as e:
                print(line)
                continue
    with open(output_file, 'w', encoding='utf-8') as file:
        for item in label:
            file.write(item + '\n')
    print("the number of label_answers: "+str(len(label)))
    return label,output_file
   

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_path', type=str, default="E:\dmt\\formula\\Direct Preference Optimization--Your Language Model is Secretly a Reward Mode.pdf", help='the input file path')
    parser.add_argument('--model_name', type=str, default="gemini-2.0-flash-exp", help='the gemini model you want to use.')
    parser.add_argument('--input_path', type=str, default="E:\dmt\\formula\\generated\\final_test\\api_Direct Preference Optimization--Your Language Model is Secretly a Reward Mode_formula.jsonl", help='input query(.jsonl)')
    parser.add_argument('--output_dir', type=str, default="E:\\dmt\\formula\\generated\\final_test", help='output dir')
    args = parser.parse_args()
    print("pdf: " + args.pdf_path)
    print("model: " + args.model_name)
    print("input math expressions(.jsonl): " + args.input_path)
    print("output_dir: " + args.output_dir)


    query = []
    with open(args.input_path, 'r', encoding='utf-8') as infile:
        for line in infile:
            # formulas.append(line)
            data = json.loads(line.strip())
            query.append(data)
            # print(formulas)
            # assert  0

    QA_path = os.path.join(args.output_dir, "api_"+args.pdf_path.split('\\')[-1][:-4]+"_QA.jsonl")
    label, outputfile = generate_label(args.model_name, query, args.pdf_path, args.output_dir)
    
