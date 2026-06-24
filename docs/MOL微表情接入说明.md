# MOL 微表情接入说明

## 快速入口

- 组会交付索引：`docs/MOL微表情组会交付包.md`
- 复现实验命令：`docs/MOL微表情复现实验命令清单.md`
- 当前组会总结：`reports/MOL微表情组会实验总结.md`
- 6 样本明细表：`reports/MOL微表情样本明细表.md`
- 批量提取结果：`reports/mol_micro_batch_samm_limit6/summary.json`
- 消融烟测结果：`reports/micro_expression_ablation_smoke/ablation_summary.json`
- 交付包自检报告：`reports/MOL微表情交付包自检报告.md`

## 当前状态

- 已接入 `MOLMicroExpressionExtractor`。
- 在线多模态服务会保存 `micro_expression_feature.json`，并在 task/report artifacts 中记录 `micro_expression_feature_path`。
- 大五报告 prompt 会读取微表情摘要，把它作为“短时面部线索”写入报告上下文。
- 训练脚本支持 `--use-micro-expression-features`，后续可以直接做“不开微表情 / 开微表情”的消融对照。
- 在线推理默认读取 `third_party/MOL/saved_models/MOL_HF_TIM20_SAMM3_26subj_fullquick_SAMM_006_3cls.pth`。该权重是本地模型产物，被 `.gitignore` 排除，部署机需要单独复制或用 `MOL_MODEL_PATH` 指向实际文件。
- 如果视频抽帧少于 8 张，MOL runner 会重复最后一帧补齐 8 帧输入；没有任何帧时仍返回失败态 JSON。

## 在线产物

`micro_expression_feature.json` 的关键字段：

- `success`：微表情模块是否成功返回结果。
- `probabilities`：`surprise / positive / negative` 三分类概率。
- `feature_vector`：给多模态 bundle 和消融训练使用的 8 维特征。
- `summary`：结构化摘要，包括主导微表情、中文标签、置信度和情绪倾向提示。
- `summary_text_zh`：适合报告和演示直接展示的中文摘要。
- `interpretation_boundary_zh`：解释边界，强调微表情只是短时面部线索。
- `errors`：MOL 不可用、超时、缺权重、缺帧等错误信息。

## 演示命令

可以用已有 SAMM 样本帧目录做一次组会演示：

```powershell
python scripts/run_micro_expression_demo.py --frames-dir third_party/MOL/data/SAMM_data_3/positive/007_6_1 --device cpu --timeout-seconds 60
```

期望输出类似：

```text
微表情提取成功
主导微表情为消极，置信度约 51/100。
特征维度：8 维
结果文件：D:\PythonCode\TestAgent\uploads\multimodal_personality\artifacts\mol_demo\features\micro_expression\micro_expression_feature.json
```

## 消融训练入口

不使用微表情：

```powershell
python scripts/train_agtn_mtl.py --train-bundle-dir <bundle_dir> --checkpoint reports/ablation/no_micro.pt
```

使用微表情：

```powershell
python scripts/train_agtn_mtl.py --train-bundle-dir <bundle_dir> --use-micro-expression-features --checkpoint reports/ablation/with_micro.pt
```

训练前可以先统计 bundle 与微表情 JSON 的覆盖情况：

```powershell
python scripts/prepare_micro_expression_ablation_manifest.py --bundle-dir <bundle_dir> --micro-expression-dir <micro_expression_dir> --output reports/micro_expression_ablation_manifest.json
```

## 降级逻辑

MOL 失败时仍会写失败态 JSON，主模型继续推理。报告生成时如果微表情模块没有可用结果，只提示“微表情模块未返回可用结果”，不会影响大五人格分数和主报告生成。

## 组会说明建议

可以这样介绍这部分：

> 我们把 MOL 作为一个可选的微表情线索模块接进在线多模态系统。当前它输出惊讶、积极、消极三类概率，并压成 8 维特征写进 bundle。主模型默认仍保持旧 checkpoint 兼容；做消融时再打开 `--use-micro-expression-features`。如果 MOL 失败，系统会记录错误但继续生成大五报告。
