* **multiple\_choice\_eval.py**

  * **作用**：用于评估选择题数据集的脚本，输入数据集文件，输出LLM选择结果文件和统计结果（正确/错误选择数及对应条目序号）。
  * **用法**：

    ```bash
       python data_evaluation/benchmark_evaluation/multiple_choice_eval.py \
       --dataset data/storm-born-choice.jsonl \
       --model gpt-4 \
       --output results/benchmark.json
    ```

*   **evaluate_fill_blanks.py**

    *   **作用**：用于评估LLMs在数学解题步骤中，推理缺失的解题步骤的能力。脚本会调用LLM在带空格的解题步骤进行填空，并自动判断生成结果的正确性。

    *   **用法**：
        1.  **准备数据**：在脚本同目录下创建 `data/storm_born_blank.jsonl` 数据文件。
        2.  **配置密钥**：在脚本中填入你的 `api_key`。
        3.  **运行脚本**：
            ```bash
            python data_evaluation/benchmark_evaluation/evaluate_fill_blanks.py
            ```
        4.  **选择模式**：根据命令行提示输入 `1` 或 `2` 选择运行模式。
            *   `1`: 标准评估模式。
            *   `2`: 实时优化评估模式（推荐）。

* **llm_as_judge.py**

  * **作用**：用于使用LLMs自动评估生成式数据集的脚本，输入数据集文件，LLMs 从 Correctness、Clarity、Completeness、Similarity 多个维度进行打分评估（0-2分）。但是实践证明 LLMs 评估不准确，总是打分极度偏高。
 
