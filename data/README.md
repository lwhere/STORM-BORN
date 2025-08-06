## 文件列表

* **storm-born.jsonl**

  * **作用**：STORM-BORN 数据集的主文件，包含原始数学推理题目及对应答案。
  * **用法**：用于LLMs微调或者基准评估（需要专家评估）。
  ```jsonc
  {
    "paper": "source of the data",
    "question": "question of the math derivation/proof",
    "whole_label": "…derivation/proof…",
  }
  ```

* **storm-born_train.jsonl**

  * **作用**：随机拆分的STORM-BORN 数据集的训练集（73条），包含原始数学推理题目及对应答案。
  * **用法**：用于LLMs微调。

* **storm-born_test.jsonl**

  * **作用**：随机拆分的STORM-BORN 数据集的测试集（27条），包含原始数学推理题目及对应答案。
  * **用法**：用于基准评估（需要专家评估）。

* **storm\_born\_abcd.jsonl**

  * **作用**：由QA形式的自动化评估难以实现，对LLMs在本数据集的生成式评估需要专家参与，因此我们将 STORM-BORN 数据集转换为multi-choice选择题格式，每道题目包含一个ground_truth（原始label），和三个易混淆的错误的推导证明过程。
  * **用法**：适用于选择题评估脚本。
  ```jsonc
  {
    "paper": "source of the data",
    "question": "question of the math derivation/proof",
    "A": "…derivation/proof…",
    "B": "…derivation/proof…",
    "C": "…derivation/proof…",
    "D": "…derivation/proof…",
    "ground-truth": "correct choice"
  }
  ```

* **storm\_born\_test\_abcd.jsonl**

  * **作用**：选择题格式的测试集，仅用于模型性能评估。
  * **用法**：在测试阶段使用此文件进行评估。

<!--
* **multiple\_choice\_eval.py**

  * **作用**：用于评估选择题数据集的脚本，输入数据集文件，输出LLM选择结果文件和统计结果（正确/错误选择数及对应条目序号）。
  * **用法**：

    ```bash
    python multiple_choice_eval.py \
      --input <数据集文件> \
      --output <输出结果文件>
    ```
  * **常用参数**：

    * `--input`：输入数据集路径。
    * `--output`：评估结果输出路径。
    * 更多参数：请运行 `python multiple_choice_eval.py --help` 查看。
## 使用示例

1. **模型微调**

   ```bash
   python train_model.py --data storm-born.jsonl --epochs 10
   ```

2. **模型评估**

   ```bash
   python multiple_choice_eval.py \
     --input storm_born_test_abcd(a_label).jsonl \
     --format abcd \
     --output eval_results.json
   ```
