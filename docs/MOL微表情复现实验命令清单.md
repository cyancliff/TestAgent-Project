# MOL 微表情复现实验命令清单

本文档记录当前已经跑通的 MOL 微表情复现、批量提取、消融烟测和报告生成命令。

## 1. 单样本 MOL demo

```powershell
python scripts/run_micro_expression_demo.py --frames-dir third_party/MOL/data/SAMM_data_3/positive/007_6_1 --device cpu --timeout-seconds 60
```

预期输出包含：

```text
微表情提取成功
特征维度：8 维
```

当前结果文件：

```text
uploads/multimodal_personality/artifacts/mol_demo/features/micro_expression/micro_expression_feature.json
```

## 2. SAMM 小批量 MOL 提取

```powershell
python scripts/extract_mol_micro_expression_batch.py --root-dir third_party/MOL/data/SAMM_data_3 --output-dir reports/mol_micro_batch_samm_limit6 --limit 6 --resume --device cpu --timeout-seconds 60
```

预期输出：

```text
samples=6 success=6 failure=0 output=reports\mol_micro_batch_samm_limit6
```

核心结果：

```text
reports/mol_micro_batch_samm_limit6/summary.json
reports/mol_micro_batch_samm_limit6/summary.csv
reports/mol_micro_batch_samm_limit6/<video_name>/micro_expression_feature.json
```

## 3. 小样本消融烟测

## 3. 生成 6 样本明细表

```powershell
python scripts/write_micro_expression_sample_table.py --batch-summary reports/mol_micro_batch_samm_limit6/summary.json --output-md reports/MOL微表情样本明细表.md --output-csv reports/mol_micro_sample_table.csv
```

结果文件：

```text
reports/MOL微表情样本明细表.md
reports/mol_micro_sample_table.csv
```

## 4. 小样本消融烟测

当前烟测使用本地生成的 synthetic bundle：

```text
reports/micro_expression_ablation_smoke_bundles/train
reports/micro_expression_ablation_smoke_bundles/val
```

运行命令：

```powershell
python scripts/run_micro_expression_ablation.py --train-bundle-dir reports/micro_expression_ablation_smoke_bundles/train --val-bundle-dir reports/micro_expression_ablation_smoke_bundles/val --output-dir reports/micro_expression_ablation_smoke --epochs 1 --batch-size 1 --device cpu --hidden-dim 16
```

核心结果：

```text
reports/micro_expression_ablation_smoke/ablation_summary.json
reports/micro_expression_ablation_smoke/no_micro/checkpoint.pt
reports/micro_expression_ablation_smoke/with_micro/checkpoint.pt
```

注意：这一步只是验证消融训练入口可以跑通，不作为最终结论。

## 5. 中文组会总结生成

```powershell
python scripts/write_micro_expression_experiment_report.py --batch-summary reports/mol_micro_batch_samm_limit6/summary.json --ablation-summary reports/micro_expression_ablation_smoke/ablation_summary.json --output reports/MOL微表情组会实验总结.md
```

结果文件：

```text
reports/MOL微表情组会实验总结.md
```

## 5. 聚焦测试

## 6. 交付包自检

```powershell
python scripts/check_micro_expression_deliverables.py --output-json reports/micro_expression_deliverable_check.json --output-md reports/MOL微表情交付包自检报告.md
```

预期输出：

```text
ready=true
```

结果文件：

```text
reports/micro_expression_deliverable_check.json
reports/MOL微表情交付包自检报告.md
```

## 7. 聚焦测试

```powershell
python -m pytest tests/test_micro_expression_batch_pipeline.py tests/test_micro_expression_ablation_runner.py tests/test_micro_expression_demo_scripts.py tests/test_big_five_reports_api.py tests/test_chat_api.py -q
```

当前验收结果：

```text
21 passed
```

## 8. 全量测试

```powershell
python -m pytest tests -q
```

当前验收结果：

```text
111 passed
```

## 9. 正式实验替换方式

正式消融时，只需要把烟测 bundle 目录换成真实训练/验证 bundle：

```powershell
python scripts/run_micro_expression_ablation.py --train-bundle-dir <真实训练bundle目录> --val-bundle-dir <真实验证bundle目录> --output-dir reports/micro_expression_ablation_real --epochs 10 --batch-size 4 --device cpu --hidden-dim 64
```

正式批量提取时，可以去掉 `--limit 6`：

```powershell
python scripts/extract_mol_micro_expression_batch.py --root-dir third_party/MOL/data/SAMM_data_3 --output-dir reports/mol_micro_batch_samm_full --resume --device cpu --timeout-seconds 60
```

如果 CPU 运行过慢，可以先用较小 limit 分段检查，再扩大样本。
