# Pipeline 项目

本项目提供一套从 PDF 中抽取数学公式、生成查询、检索答案、收集上下文、优化问题再到数据过滤的全流程脚本。z整体入口脚本为 `pipeline.py`，依赖同目录下的多个模块完成各个子任务。

---

## 目录结构

<!--├── clean_data.py                   # （预留）清洗、预处理中间数据脚本-->
```
├── __pycache__/                    # Python 缓存目录
├── __init__.py                     # 包初始化文件
├── answer_retriever.py             # 根据 query 调用接口检索并生成答案标签
├── context_collector.py            # 收集每个问题的上下文信息
├── filter.py                       # 对最终 JSONL 结果进行过滤、重命名
├── generate_v1.py                  # （预留）旧版或实验性 query 生成脚本
├── math_expression_extractor.py    # 从 PDF 中抽取数学公式的工具
├── pipeline.py                     # 主流程脚本，按顺序调用各模块
├── query_gen.py                    # 根据公式生成检索 query
├── question_refiner.py             # 对检索到的上下文和问题进行精炼
└── tmp.jsonl                       # （示例）临时数据存储文件
```

---

## 安装依赖

```bash
# 建议在虚拟环境中安装
pip install \
    google-generativeai \
    openai \
    typing-extensions
```

> **备注**
>
> * `google-generativeai`：用于调用 Gemini 系列模型
> * `openai`：用于调用 OpenAI 接口
> * `typing-extensions`：提供类型扩展支持

---

## 使用方法

```bash
python pipeline.py \
    --pdf_path   "/path/to/your/document.pdf" \
    --model_name "gemini-2.0-flash-exp" \
    --output_dir "/path/to/output/dir"
```

* `--pdf_path`：输入 PDF 文件的路径
* `--model_name`：要调用的语言模型名称（如 `gemini-2.0-flash-exp`）
* `--output_dir`：所有中间产物和最终结果的输出目录

执行后，脚本会依次完成以下阶段，并在控制台打印每个阶段耗时：

1. **抽取公式** – 调用 `math_expression_extractor.extract_formula`，输出 `*_formula.jsonl`
2. **生成查询** – 调用 `query_gen.generate_query`，输出 `*_query.jsonl`
3. **生成标签** – 调用 `answer_retriever.generate_label`，输出 `*_QA.jsonl`
4. **收集上下文** – 调用 `context_collector.context_collect`，输出 `*_context.jsonl`
5. **精炼问题** – 调用 `question_refiner.refine`，输出 `*_refined.jsonl`
6. **过滤数据** – 调用 `filter.filter_jsonl`，对结果中符合条件的条目进行筛选，最终写入 `deepseek-chat.jsonl` 或自定义文件名

---

## 各模块功能简介

* **`math_expression_extractor.py`**
  从 PDF 中抽取数学表达式、公式并保存为 JSONL。

* **`query_gen.py`**
  将抽取到的公式转化为检索 query。

* **`answer_retriever.py`**
  根据 query 调用深度搜索或模型接口，生成候选答案标签。

* **`context_collector.py`**
  为每对（公式，答案）检索相关上下文内容。

* **`question_refiner.py`**
  对初步生成的问题和上下文进行再加工、精炼。

* **`filter.py`**
  对最终 JSONL 数据按标签、格式等条件进行过滤整理，输出可直接用于下游任务的文件。

* **`clean_data.py` & `generate_v1.py`**
  项目早期或备用脚本，可根据需要自行扩展或清理无用中间文件。

---

## 输出示例

假设输入文件为 `Direct Preference Optimization.pdf`，输出目录为 `./generated/`，则可在 `generated/` 下看到：

```
api_Direct Preference Optimization_formula.jsonl
api_Direct Preference Optimization_query.jsonl
api_Direct Preference Optimization_QA.jsonl
api_Direct Preference Optimization_context.jsonl
api_Direct Preference Optimization_refined.jsonl
deepseek-chat.jsonl
```

---

## 致谢

本项目调用了 Google Gemini 与 OpenAI 接口，感谢相关团队提供的强大模型支持。
