* **multiple\_choice\_eval.py**

  * **作用**：用于评估选择题数据集的脚本，输入数据集文件，输出LLM选择结果文件和统计结果（正确/错误选择数及对应条目序号）。
  * **用法**：

    ```bash
       python data_evaluation/benchmark_evaluation/multiple_choice_eval.py \
       --dataset data/storm-born-choice.jsonl \
       --model gpt-4 \
       --output results/benchmark.json
    ```

* **llm_as_judge.py**

  * **作用**：用于使用LLMs自动评估生成式数据集的脚本，输入数据集文件，LLMs 从 Correctness、Clarity、Completeness、Similarity 多个维度进行打分评估（0-2分）。但是实践证明 LLMs 评估不准确，总是打分极度偏高。
 
