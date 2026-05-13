# MOL 微表情组会交付包

## 1. 当前结论

MOL 微表情 baseline 已经从“能单独跑”推进到“能进入主系统、能批量产出、能做小样本消融入口、能写进报告”的状态。

本轮最重要的验收结果：

- 真实 MOL 单样本 demo 已跑通，输出 8 维微表情特征。
- SAMM 帧目录小批量提取已跑通：6 个样本，6 个成功，0 个失败。
- 多模态在线服务会保存 `micro_expression_feature.json`。
- 报告 API 会返回结构化 `micro_expression_summary`。
- 聊天上下文会把微表情写成“短时面部线索”，不会把它当成稳定人格结论。
- 已提供 `no_micro` / `with_micro` 两组小样本消融 runner，后续可以替换成正式 bundle 数据继续训练。

## 2. 已完成代码入口

| 模块 | 文件 | 作用 |
| --- | --- | --- |
| MOL 单样本封装 | `multimodal_personality/feature_extractors/micro_expression_extractor.py` | 给主系统调用 MOL，产出统一 JSON |
| MOL 单样本推理 | `multimodal_personality/feature_extractors/mol_single_infer.py` | 在 MOL 独立环境里执行真实推理 |
| 批量提取 | `scripts/extract_mol_micro_expression_batch.py` | 扫描帧目录，批量生成微表情 JSON、CSV、summary |
| 在线服务接入 | `app/services/multimodal_personality_service.py` | 在线多模态任务中保存微表情 artifact |
| API 摘要 | `app/services/micro_expression_summary_service.py` | 把 `micro_expression_feature.json` 转成前端/聊天可读结构 |
| 报告响应 | `app/api/multimodal_personality.py` | 返回 `micro_expression_summary` |
| 聊天上下文 | `app/api/chat.py` | 将微表情作为有边界的短时线索放入对话上下文 |
| 消融 runner | `scripts/run_micro_expression_ablation.py` | 跑 `no_micro` / `with_micro` 两组实验 |
| 报告生成 | `scripts/write_micro_expression_experiment_report.py` | 生成中文组会实验总结 |

## 3. 已生成结果文件

| 结果 | 路径 |
| --- | --- |
| 单样本 MOL demo JSON | `uploads/multimodal_personality/artifacts/mol_demo/features/micro_expression/micro_expression_feature.json` |
| 6 样本批量 summary | `reports/mol_micro_batch_samm_limit6/summary.json` |
| 6 样本批量 CSV | `reports/mol_micro_batch_samm_limit6/summary.csv` |
| 每个样本的微表情 JSON | `reports/mol_micro_batch_samm_limit6/<video_name>/micro_expression_feature.json` |
| 6 样本展示 Markdown | `reports/MOL微表情样本明细表.md` |
| 6 样本展示 CSV | `reports/mol_micro_sample_table.csv` |
| 消融烟测 summary | `reports/micro_expression_ablation_smoke/ablation_summary.json` |
| no_micro checkpoint | `reports/micro_expression_ablation_smoke/no_micro/checkpoint.pt` |
| with_micro checkpoint | `reports/micro_expression_ablation_smoke/with_micro/checkpoint.pt` |
| 中文组会总结 | `reports/MOL微表情组会实验总结.md` |
| 交付包自检 JSON | `reports/micro_expression_deliverable_check.json` |
| 交付包自检报告 | `reports/MOL微表情交付包自检报告.md` |

## 4. 当前实验数字

### 批量 MOL 提取

数据来源：`third_party/MOL/data/SAMM_data_3`

当前小批量设置：`--limit 6`

结果：

- 样本数：6
- 成功数：6
- 失败数：0
- 主导微表情分布：`negative: 6`
- 置信度大约集中在 `0.512` 到 `0.515`

这个结果说明 MOL 推理链路稳定跑通，但不能说明模型在完整数据集上的最终性能，因为当前只取了 6 个样本做演示闭环。

### 小样本消融烟测

当前消融用的是 synthetic bundle，目的只是验证训练入口，不作为论文结论。

| Run | 是否接入微表情 | Best Loss | MAE | PCC | ACC |
| --- | --- | ---: | ---: | ---: | ---: |
| no_micro | 否 | 0.0067 | 0.0687 | 0.3985 | 0.9313 |
| with_micro | 是 | 0.0160 | 0.1137 | 0.2959 | 0.8863 |

解释方式：这组数字只能说明消融代码链路已经可运行。由于数据是极小 synthetic 样本，不能据此判断“微表情有效”或“微表情无效”。正式汇报时要强调后续会替换成真实 bundle 和固定随机种子重复实验。

## 5. 组会汇报说法

可以这样讲：

1. 我们选了 MOL 作为微表情 baseline，因为它是近期 TPAMI 方向的微表情识别工作，适合作为已发表方法复现。
2. 我没有改 MOL 网络结构，而是先把它做成主系统可调用的可选模块，保证不会破坏原来的多模态人格模型。
3. 目前 MOL 已经能在 SAMM 帧目录上批量提取，统一输出 `micro_expression_feature.json`。
4. 主系统已经能保存微表情结果，报告 API 和聊天上下文都可以读取结构化摘要。
5. 消融入口已经准备好：`no_micro` 是原多模态模型，`with_micro` 是增加微表情特征分支后的模型。
6. 当前消融结果只是烟测，证明训练流程能跑；下一步会扩大真实 bundle 样本，做正式重复实验。

## 6. 解释边界

微表情只适合作为短时间面部状态线索，不能直接等同于稳定人格标签。

组会中建议明确说：

- MOL 输出的是微表情分类和短时情绪倾向，不是人格判断。
- 人格结论仍然以多模态主模型和大五报告为主。
- 微表情模块的价值在于提供额外视觉线索，并通过消融实验验证它是否能改善最终人格预测指标。

## 7. 后续正式实验

建议下一轮做三件事：

1. 把 `--limit 6` 扩大到完整可用 SAMM/TIM20 帧目录，生成完整微表情特征库。
2. 用真实 CFI/TIM20 对齐后的 bundle 跑 `no_micro` / `with_micro`，固定随机种子重复 3 到 5 次。
3. 汇总 MAE、ACC、PCC、CCC、R2，并补一张表说明微表情分支是否带来稳定提升。
