# 20 人真实用户 ATMR 多源证据验证实验计划

## 1. 实验定位

本实验定位为小规模真实用户验证实验，用于验证系统在真实用户场景下的可用性、多源证据一致性和 AERI / MEG 指标的解释价值。

需要注意，本实验不用于证明 ATMR 量表具有正式心理测量学效度，也不用于证明多模态和微表情能够直接提高 ATMR 测评准确率。

更准确的研究目标是：

> 在真实用户样本中，验证多模态 Big Five 和微表情线索能否作为 ATMR 主测评之外的辅助证据链，帮助系统判断报告是否可以强解释，或者是否需要谨慎解释。

因此，本文仍以 ATMR 作为主测评结果，多模态 Big Five 与微表情只参与报告解释可靠性的量化评估，不改写 ATMR 原始得分。

## 2. 实验目标

本实验包含四个目标：

1. 验证 ATMR 主测评流程能在真实用户上稳定完成。
2. 验证多模态 Big Five 与 ATMR 之间是否存在可解释的一致性或张力。
3. 验证微表情是否可以作为短时状态风险线索，辅助判断报告解释边界。
4. 使用 AERI / MEG 指标量化多模态和微表情对 ATMR 报告可信度的辅助价值。

## 3. 参与者设计

计划招募 20 名真实用户参与实验，参与者统一匿名编号：

```text
P01 - P20
```

建议招募条件：

| 项目 | 要求 |
|---|---|
| 年龄 | 18 岁及以上 |
| 来源 | 同学、朋友或自愿参与者 |
| 设备 | 能完成网页测评并上传短视频 |
| 排除条件 | 不愿上传视频、不愿填写反馈问卷、当前状态明显不适者 |

论文和实验表格中只使用匿名编号，不记录姓名、手机号、身份证号、头像等个人隐私信息。

## 4. 实验前说明

实验开始前，需要向参与者说明：

```text
本系统结果仅用于毕业设计研究和系统验证，不作为医学诊断、心理诊断或正式人格评估依据。
```

还需要说明：

```text
1. 参与者可以自愿参与或退出。
2. 上传视频仅用于本次系统验证。
3. 论文中只展示匿名统计结果，不展示个人身份信息。
4. 测评报告反映的是倾向性结果，不代表固定人格标签。
```

## 5. 单个参与者实验流程

每名参与者完成四个步骤：

```text
1. 完成 ATMR 在线测评。
2. 上传一段 30-60 秒自拍视频。
3. 完成简短 Big Five 自评问卷。
4. 查看系统报告后填写反馈问卷。
```

建议实验顺序如下：

| 步骤 | 操作 | 产出 |
|---|---|---|
| 1 | 创建匿名编号 | P01 - P20 |
| 2 | 完成 ATMR 测评 | ATMR 四维得分、作答可信度 |
| 3 | 上传自拍视频 | 多模态 Big Five、微表情结果 |
| 4 | 填写 Big Five 自评 | 外部参照数据 |
| 5 | 查看报告 | 用户主观理解 |
| 6 | 填写反馈问卷 | 报告符合度和可信度评分 |

## 6. 视频采集规范

为了降低视频质量差异对多模态结果的影响，建议统一视频采集要求：

| 项目 | 要求 |
|---|---|
| 时长 | 30-60 秒 |
| 画面 | 正脸出镜，面部无遮挡 |
| 光线 | 光线正常，避免过暗或强逆光 |
| 声音 | 尽量在安静环境录制 |
| 内容 | 回答固定问题 |

推荐固定视频问题：

```text
请简单介绍一下你自己，并说说你最近一次完成重要任务的经历。
```

选择该问题的原因是：它能诱发一定的自我描述、表达风格、任务执行和压力回忆线索，适合多模态 Big Five 与微表情模块提取辅助证据。

## 7. 需要采集的数据字段

每名参与者建议整理为一行数据。

### 7.1 基础信息

| 字段 | 示例 | 说明 |
|---|---|---|
| participant_id | P01 | 匿名编号 |
| completed_atmr | true | 是否完成 ATMR |
| uploaded_video | true | 是否上传视频 |
| completed_feedback | true | 是否完成反馈问卷 |

### 7.2 ATMR 数据

| 字段 | 来源 | 说明 |
|---|---|---|
| atmr_A_score | ATMR 报告 | 欣赏型得分 |
| atmr_T_score | ATMR 报告 | 目标型得分 |
| atmr_M_score | ATMR 报告 | 包容型得分 |
| atmr_R_score | ATMR 报告 | 责任型得分 |
| atmr_dominant_type | ATMR 报告 | 主导维度 |
| atmr_confidence | `trust_summary.assessment_confidence` | ATMR 原始可信度 |
| anomaly_count | `trust_summary.anomaly_count` | 异常作答数量 |

### 7.3 多模态 Big Five 数据

| 字段 | 来源 | 说明 |
|---|---|---|
| openness | Big Five 报告 | 开放性 |
| conscientiousness | Big Five 报告 | 尽责性 |
| extraversion | Big Five 报告 | 外向性 |
| agreeableness | Big Five 报告 | 宜人性 |
| neuroticism | Big Five 报告 | 神经质 |
| multimodal_quality | `quality_summary.overall_quality` | 多模态输入质量 |
| multimodal_confidence | `confidence_summary.overall_confidence` | Big Five 预测置信度 |
| atmr_bigfive_consistency | `consistency_summary.overall_score` | ATMR 与 Big Five 一致性 |

### 7.4 微表情数据

| 字段 | 来源 | 说明 |
|---|---|---|
| micro_dominant | 微表情结果 | 主导微表情 |
| micro_confidence | 微表情结果 | 主导类别置信度 |
| micro_positive | 微表情结果 | 正向概率 |
| micro_negative | 微表情结果 | 负向概率 |
| micro_surprise | 微表情结果 | 惊讶概率 |
| micro_risk | 公式计算 | 短时状态风险 |
| micro_stability | 公式计算 | 短时状态稳定度 |

### 7.5 综合指标

| 字段 | 说明 |
|---|---|
| E_bf | Big Five 跨证据支持项 |
| E_micro | 微表情状态支持项 |
| AERI | ATMR 多源证据可靠性指数 |
| MEG | 多源证据增益指数 |
| reliability_level | 强证据支持 / 中等支持 / 谨慎解释 |

### 7.6 用户反馈数据

| 字段 | 评分范围 | 说明 |
|---|---:|---|
| feedback_atmr_fit | 1-5 | ATMR 报告符合程度 |
| feedback_bigfive_fit | 1-5 | 视频 Big Five 报告符合程度 |
| feedback_video_helpful | 1-5 | 加入视频分析后是否更有参考价值 |
| feedback_boundary_clear | 1-5 | 报告是否清楚说明使用边界 |
| feedback_willing_to_use | 1-5 | 是否愿意作为自我了解工具 |
| feedback_comment | 文本 | 开放反馈 |

## 8. 指标计算方法

### 8.1 ATMR 原始可信度

```text
A = atmr_confidence
```

对应系统字段：

```text
trust_summary.assessment_confidence
```

### 8.2 Big Five 跨证据支持项

设：

```text
C = atmr_bigfive_consistency
Q = multimodal_quality
P = multimodal_confidence
```

则：

```text
E_bf = Q × P × (2C - 1)
```

解释：

| 条件 | 含义 |
|---|---|
| C > 0.5 | Big Five 倾向于支持 ATMR |
| C = 0.5 | Big Five 对 ATMR 基本中性 |
| C < 0.5 | Big Five 与 ATMR 存在张力 |
| Q 或 P 较低 | 多模态证据影响自动减弱 |

### 8.3 微表情状态支持项

设：

```text
negative = micro_negative
surprise = micro_surprise
positive = micro_positive
conf = micro_confidence
```

短时状态风险：

```text
micro_risk = conf × (0.7 × negative + 0.3 × surprise) × (1 - 0.5 × positive)
```

短时状态稳定度：

```text
micro_stability = 1 - micro_risk
```

微表情状态支持项：

```text
E_micro = conf × (2 × micro_stability - 1)
```

说明：

```text
E_micro > 0：当前面部状态相对稳定，可轻微支持报告解释。
E_micro = 0：微表情线索中性。
E_micro < 0：短时负向或惊讶状态较强，报告应谨慎解释。
```

### 8.4 AERI 与 MEG

ATMR 多源证据可靠性指数：

```text
AERI = clamp(A + 0.25 × E_bf + 0.10 × E_micro, 0, 1)
```

多源证据增益指数：

```text
MEG = AERI - A
```

分级规则：

| AERI 范围 | 等级 | 报告解释策略 |
|---:|---|---|
| AERI >= 0.80 | 强证据支持 | 可以正常解释 ATMR 主画像 |
| 0.60 <= AERI < 0.80 | 中等证据支持 | 需要保留边界说明 |
| AERI < 0.60 | 证据不足或存在张力 | 建议谨慎解释、复测或结合更多证据 |

MEG 解释规则：

| MEG 范围 | 含义 |
|---:|---|
| MEG >= 0.05 | 辅助证据增强 ATMR 报告 |
| -0.05 < MEG < 0.05 | 辅助证据基本中性 |
| MEG <= -0.05 | 辅助证据提示存在张力 |

## 9. 实验对照组设计

为了体现辅助证据的增益，可以构建三组对照。

| 组别 | 使用信息 | 指标 |
|---|---|---|
| ATMR-only | 只使用 ATMR 可信度 | `A` |
| ATMR + Big Five | 加入 Big Five 一致性、质量和置信度 | `clamp(A + 0.25 × E_bf, 0, 1)` |
| ATMR + Big Five + Micro | 加入 Big Five 与微表情 | `AERI` |

比较方式：

```text
ATMR + Big Five 相比 ATMR-only 的提升
ATMR + Big Five + Micro 相比 ATMR + Big Five 的变化
完整 AERI 相比 ATMR-only 的 MEG
```

## 10. 统计分析方案

由于样本量为 20，建议使用描述性统计，不做夸大的显著性结论。

### 10.1 完成情况统计

| 指标 | 说明 |
|---|---|
| 总参与人数 | 20 |
| ATMR 完成人数 | 完成主测评的人数 |
| 视频上传成功人数 | 成功上传视频的人数 |
| 多模态推理成功人数 | 成功生成 Big Five 报告的人数 |
| 微表情提取成功人数 | 成功生成微表情结果的人数 |
| 反馈问卷回收人数 | 完成主观反馈的人数 |

### 10.2 AERI / MEG 统计

| 指标 | 说明 |
|---|---|
| mean(AERI) | 平均多源证据可靠性 |
| std(AERI) | AERI 标准差 |
| mean(MEG) | 平均辅助证据增益 |
| MEG >= 0.05 人数 | 辅助证据增强样本数 |
| MEG <= -0.05 人数 | 跨证据张力样本数 |
| AERI >= 0.80 人数 | 强证据支持样本数 |
| AERI < 0.60 人数 | 谨慎解释样本数 |

### 10.3 ATMR 与 Big Five 一致性统计

| 指标 | 说明 |
|---|---|
| mean(C) | 平均 ATMR-Big Five 一致性 |
| std(C) | 一致性标准差 |
| C >= 0.70 人数 | 高一致性样本 |
| C < 0.50 人数 | 存在张力样本 |

### 10.4 微表情状态统计

| 指标 | 说明 |
|---|---|
| dominant negative 人数 | 负向主导样本数 |
| dominant positive 人数 | 正向主导样本数 |
| dominant surprise 人数 | 惊讶主导样本数 |
| mean(micro_risk) | 平均短时状态风险 |
| mean(micro_stability) | 平均短时状态稳定度 |
| 高状态风险人数 | micro_risk 较高的样本数 |

### 10.5 用户反馈统计

| 指标 | 说明 |
|---|---|
| mean(feedback_atmr_fit) | ATMR 报告符合度均值 |
| mean(feedback_bigfive_fit) | Big Five 报告符合度均值 |
| mean(feedback_video_helpful) | 视频辅助可信度均值 |
| mean(feedback_boundary_clear) | 报告边界清晰度均值 |
| mean(feedback_willing_to_use) | 用户使用意愿均值 |

## 11. 结果表格模板

### 11.1 参与者级结果表

| ID | A | C | Q | P | Micro Stability | AERI | MEG | 等级 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| P01 | 0.82 | 0.76 | 0.88 | 0.80 | 0.79 | 0.94 | +0.12 | 强证据支持 |
| P02 | 0.78 | 0.42 | 0.85 | 0.75 | 0.61 | 0.66 | -0.12 | 中等支持 |
| P03 | 0.55 | 0.70 | 0.60 | 0.58 | 0.80 | 0.63 | +0.08 | 中等支持 |

### 11.2 汇总统计表

| 指标 | 数值 |
|---|---:|
| 样本数 | 20 |
| 平均 AERI |  |
| 平均 MEG |  |
| MEG >= 0.05 人数 |  |
| MEG <= -0.05 人数 |  |
| AERI >= 0.80 人数 |  |
| AERI < 0.60 人数 |  |
| 平均用户报告符合度 |  |
| 平均视频辅助可信度 |  |

## 12. 时间安排

建议按 7 天完成。

| 时间 | 任务 |
|---|---|
| 第 1 天 | 准备实验说明、匿名编号表、反馈问卷、数据记录表 |
| 第 2-3 天 | 招募并完成 20 人 ATMR 测评和视频上传 |
| 第 4 天 | 导出 ATMR、多模态、微表情结果 |
| 第 5 天 | 计算 AERI / MEG，整理统计表 |
| 第 6 天 | 写入论文实验分析小节 |
| 第 7 天 | 检查隐私、截图、补充附录和答辩材料 |

## 13. 最终产物

本实验结束后应形成以下产物：

```text
1. 20 人匿名实验数据表
2. AERI / MEG 指标计算表
3. 用户反馈问卷统计表
4. 真实用户小样本验证实验章节
5. 答辩展示用实验结果截图
```

## 14. 论文写法建议

如果多数样本 MEG 为正，可以写：

> 在 20 名真实用户的小样本实验中，多数样本在加入多模态与微表情辅助证据后获得正向 MEG，说明外部行为线索能够在一定程度上增强 ATMR 报告的解释支持。

如果部分样本 MEG 为负，可以写：

> 实验结果显示，多模态与微表情并非总是增强 ATMR 结论。当跨来源结果存在张力时，AERI 能够降低报告解释强度，从而避免系统对低一致性样本进行过度解释。

更稳妥的综合写法：

> 本实验不是为了证明 ATMR 量表的正式心理测量学效度，而是通过 20 名真实用户验证系统的完整测评流程、多源证据采集能力和 AERI / MEG 指标的解释价值。结果可用于说明多模态 Big Five 与微表情线索能够作为 ATMR 主报告之外的辅助证据链，帮助系统进行解释增强、冲突提示和边界控制。

## 15. 答辩回答建议

如果老师问：

```text
20 个人够不够证明 ATMR 有效？
```

可以回答：

> 20 人样本不足以证明 ATMR 量表的正式心理测量学效度，因此本文没有做这样的宣称。该实验定位为小规模真实用户验证，主要用于验证系统流程可用性、多源证据采集能力和 AERI / MEG 指标是否能反映辅助证据对报告解释可靠性的影响。

如果老师问：

```text
多模态和微表情到底对 ATMR 有什么帮助？
```

可以回答：

> 本系统没有用多模态和微表情替代 ATMR 主评分，而是将它们作为辅助证据链。多模态 Big Five 用于判断 ATMR 结果是否获得跨来源支持，微表情用于识别短时状态风险。当辅助证据一致时，系统提高解释可靠性；当辅助证据冲突或质量较低时，系统降低解释强度并提示谨慎使用。

如果老师问：

```text
为什么不直接证明多模态提高 ATMR 准确率？
```

可以回答：

> 因为 ATMR、多模态 Big Five 和微表情并不共享同一套标签体系，且当前没有大规模真实人格真值数据。直接声称提高 ATMR 准确率是不严谨的。因此本文采用更稳妥的证据链视角，量化外部线索是否增强报告解释可靠性或提示解释风险。

