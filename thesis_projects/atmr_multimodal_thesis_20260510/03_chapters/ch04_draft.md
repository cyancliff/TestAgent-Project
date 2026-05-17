# 第4章 关键模块设计与实现
<!-- chapter_id: ch_4 -->

## 4.1 用户认证与测评会话实现

用户认证模块为整个系统提供访问入口。用户登录后，前端将认证状态用于控制测评、历史记录、聊天和大五人格报告访问。后端通过依赖注入获取当前用户，并在每个需要用户资源的接口中校验所有权。该设计使认证逻辑与业务逻辑保持分离，也便于后续扩展权限控制。

测评会话实现采用“草稿准备 + 有效记录持久化”的策略。用户点击开始测评时，系统先检查是否存在活跃会话，若存在则返回冲突信息，由前端提示用户继续、覆盖或修改。真正保存会话和答题记录发生在用户进入实质作答之后，这样可以减少空会话和无效历史记录。

恢复会话接口会读取当前用户最新活跃会话、已答题记录和对应题目信息，再返回当前阶段、已提交阶段、答题数量、答案列表和题目列表。前端据此恢复页面状态，使用户可以从上次中断处继续。这一功能对于完整测评系统非常重要，因为心理测评通常需要十几分钟，用户中途离开是常见情况。

## 4.2 自适应选题模块实现

自适应选题模块集中在 app/services/question_selection.py。实现时我没有把选题写成单纯“随机抽下一题”，而是先用已答题目的 feature_vector 计算用户画像，再根据能力估计和候选题属性排序。服务入口 select_next_question 会接收 user_id、session_id、answered_question_ids、module 和 transient_records，其中 transient_records 是为了支持前端阶段内临时作答场景，避免还没提交数据库时无法计算下一题。

能力估计使用 0.5 均值、0.25 方差作为初始先验。每条 AnswerRecord 会提供 score、is_anomaly 和 exam_no，服务再根据 exam_no 找到 Question 中的 difficulty、discrimination 和 feature_vector。异常作答不会被完全丢弃，而是把权重降到 0.5，同时把观测精度降低。这一点和报告解释中的“异常只提示风险，不直接否定答案”保持一致。

候选题评分由 Fisher 信息量、覆盖度、难度匹配和区分度组成。实现里还有一个不确定性比例 uncertainty_ratio：前几题不确定性高时，Fisher 信息量和区分度权重大；后面能力估计稳定后，覆盖度权重提高，避免候选题一直围绕相似向量。这个细节是为了让测评既能快速定位，也能覆盖更多特征面。

[[EQ:S(q)=w_1I(q)+w_2C(q)+w_3D(q)+w_4R(q)]]

其中，I(q) 表示 Fisher 信息量，C(q) 表示覆盖度，D(q) 表示难度匹配，R(q) 表示区分度。公式只是对实现逻辑的概括，实际代码中还包含候选题为空、首次选题、模块过滤和向量缺失等分支处理。

## 4.3 异常作答检测模块实现

异常作答检测模块由 ai_detector 服务实现。当前版本有意保留较少规则，主要检测明显过快作答。系统将平均作答时间做下界归一化，若某题作答时间低于平均时间的 10%，则标记为异常，并返回风险分数、原因列表和追问问题。

这种实现看似简单，但符合当前阶段的工程目标。测评系统的异常检测如果规则过多，容易在没有充分验证的情况下误伤用户。本文选择先实现一个明确、可解释、易测试的规则，再将结果作为报告的可信度提示。后续可以在日志数据充足后扩展连续快速作答、重复选项、极端分布和前后矛盾等规则。

异常检测结果不会直接改变分数，而是影响解释和选题权重。自适应选题模块会降低异常记录的画像权重，报告生成模块也可以提醒用户相关维度需要谨慎解读。这样的设计避免了将单一行为指标直接等同于人格特征。

## 4.4 多智能体辩论与 RAG 实现

多智能体辩论模块由 debate_manager 组织。系统将 ATMR 四个模块的裁判总结作为上下文，并设置正方、反方和裁判三类角色。正方从结构优势和发展潜力出发，反方从风险和边界出发，裁判综合双方意见并给出最终结论。实现上，系统使用并发执行第一轮发言，再由裁判进行中场建议和综合。

RAG 服务基于 PageIndex。系统维护 ATMR 知识库和 Big Five 知识库，先根据查询进行关键词粗筛，再在候选章节中进行语义评分，并返回相关证据。若外部模型不可用，系统会回退到关键词评分，保证服务不会因检索模型失败而完全中断。

在报告生成中，RAG 的价值并不是简单给模型附加更多文本，而是让分析过程能够引用与用户数据相关的知识片段。多智能体辩论结合 RAG 后，报告能够同时体现积极解释、风险提醒和知识依据。对于心理测评类系统，这种结构比单次大模型生成更容易控制语气和边界。

## 4.5 多模态特征提取与 Feature Bundle 实现

多模态特征提取最容易出问题的地方不是模型结构，而是输入格式不统一。一个视频样本会产生图像帧、音频、转写文本、CLIP 视觉特征、CLIP 文本特征、wav2clip 音频特征和 bg_features。如果训练脚本、评估脚本和在线服务各自组织这些字段，后续一定会出现维度错位或标签顺序错位。

因此项目在 multimodal_personality/models/feature_bundle.py 中定义了 MultimodalFeatureBundle。当前契约规定 clip_video 为 15 帧、每帧 768 维；clip_text 最多 13 句、每句 768 维；wav2clip 为 15 段、每段 512 维；bg_features 为 256 维；micro_expression_features 可选，为 8 维；labels 按 openness、conscientiousness、extraversion、agreeableness、neuroticism 排列。

bundle 的 validate 和 to_tensors 两个方法在开发中很有用。validate 会提前检查维度是否符合预期，to_tensors 会把不足的序列补零或截断到固定长度。在线推理时，如果某个模态缺失，服务可以明确决定是失败还是填充，而不是让 PyTorch 在模型前向时才报一个难定位的 shape 错误。

这个设计也方便论文实验复盘。训练、评估和在线 smoke 使用的都是同一种 bundle 文件，因此当报告中写到某个 checkpoint 的测试结果时，可以追溯到对应的 manifest、bundle 目录和评估 JSON，而不是只剩一个孤立的指标表。

## 4.6 AGTN-MTL Baseline 模型实现

AGTN-MTL baseline 的代码位于 multimodal_personality/models/agtn_mtl.py。模型输入包含 clip_video、wav2clip、clip_text、bg_features 和可选 micro_expression_features，输出是 Big Five 五维分数。它参考了多模态人格预测论文中的图结构和多任务思想[[REF:1]]，但实现上更偏向当前仓库能稳定训练和接入的版本。

文本分支使用 SequenceEncoder 和 TemporalAttention，对 CLIP 文本句子序列做编码；视觉分支先加位置编码，再经过两层 GraphConvBlock 和线性投影；音频分支对 wav2clip 序列采用类似处理。视觉和音频池化后通过 cosine_feature_fusion 形成 video_audio 表示。最后，ResidualChannelAttention 把 bg_feature、video_audio、text 和可选 micro_feature 融合，再由主预测头输出 0 到 1 的五维分数。

模型还保留 bg_output、audio_output、text_output 和 micro_output 等辅助头。当前训练主要使用主任务回归，辅助头更多是为后续多任务损失预留结构。这个边界必须写清楚：当前结果能证明工程 baseline 可运行、可评估、可接入，但不能说已经完整复现原论文的全部多任务训练策略。

实际接入时，服务层通过 load_checkpoint_model 恢复模型和 model_kwargs。当前在线默认模型版本是 agtn-mtl-best-lr1e4-drop02，对应 checkpoint 路径为 reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt。报告页会显示模型版本，便于后续比较不同 checkpoint 的输出差异。

## 4.7 大五人格报告与前端展示实现

大五人格报告页对应 frontend/src/components/BigFiveReport.vue。页面加载后先根据 report_id 请求报告详情，如果 status 还在 running，就显示刷新和返回历史入口；如果已经 completed 且存在 scores，就展示雷达图、五维分数条、维度水平、报告来源和 AI 解读。这个页面的重点不是炫图，而是让用户知道结果来自哪个视频、哪个模型版本、是否是真实模型输出。

报告来源区域会显示 original_filename、model_version 和 is_real_result。这个字段很关键，因为项目早期有 scaffold 和 fallback 输出，如果不区分，用户可能把占位分数当成真实人格结果。后端 _is_real_result 会检查任务状态、分数和模型版本，只有真实 checkpoint 的完成结果才进入正式解读。

聊天页对应 Chat.vue。它不是把所有历史报告自动塞进提示词，而是提供两个下拉框：一个关联 ATMR 报告，一个关联大五人格报告。用户可以不关联、只关联其中一种，或者同时关联两种。这个设计在使用上多一步选择，但能让咨询上下文更透明，也避免把不同来源的证据混成一个模糊结论。

## 4.8 本章小结

本章从实现角度介绍了系统关键模块。ATMR 主线实现了认证、会话、阶段作答、自适应选题、异常检测、多智能体辩论和 RAG；多模态辅线实现了特征提取、feature bundle、AGTN-MTL baseline、在线推理和大五人格报告。两个子系统通过报告和聊天上下文建立联系，但在数据模型、任务状态和解释边界上保持独立。

## 4.9 部署运行与工程治理实现

除功能模块外，系统还需要具备可部署和可维护能力。本文项目提供 Dockerfile、docker-compose.yml、后端健康检查接口和前端 nginx 配置，使在线主系统可以在容器环境中运行。后端根路径返回服务启动信息，/health 接口会检查数据库连接状态，为部署探针和运维检查提供基础。

配置管理方面，系统将项目名称、数据库连接、允许跨域来源、多模态目录、checkpoint 路径、运行设备和外部模型配置集中在配置层。这样可以避免业务代码中散落硬编码路径，也便于在本地开发、离线训练和线上部署之间切换。多模态路径使用项目根目录解析相对路径，减少不同终端工作目录造成的路径错误。

多模态运行环境与主系统运行环境存在明显差异。离线训练依赖 torch、CUDA、ffmpeg、CLIP、wav2clip 和较大的数据集文件，而在线主系统更强调启动稳定和响应速度。因此，本文将多模态依赖单独列入 requirements_multimodal.txt，并在服务层对依赖可用性进行检测。即使多模态模块加载失败，主系统仍可跳过相关路由继续启动。

测试治理方面，项目 tests 目录覆盖了认证、聊天、RAG、题目选择、问题清洗、项目健康、多模态训练管线、多模态服务、模型结构、特征提取器和大五报告接口等内容。对于毕业设计项目而言，测试不仅用于发现错误，也能证明系统不是只在演示路径下偶然可用，而是具备一定回归验证基础。

工程文档也是治理的一部分。项目中 README、部署文档、开发者日志、毕设进度、多模态复现汇报和待完成任务共同记录了系统当前状态、运行方式、已完成内容和未完成边界。论文写作时引用这些材料，可以使章节内容与实际工程进度保持一致，避免论文描述超前于代码实现。

## 4.10 关键实现文件对应关系

为了让论文描述和代码对应起来，本文整理了几个关键文件。app/api/assessment/sessions.py 负责测评会话开始、恢复、重启和删除；app/services/question_selection.py 负责自适应选题；app/services/ai_detector.py 负责异常作答检测；app/services/debate_manager.py 负责多智能体辩论；app/services/rag_service.py 负责 PageIndex 检索。

多模态部分中，multimodal_personality/models/feature_bundle.py 定义输入契约，multimodal_personality/models/agtn_mtl.py 定义模型结构，multimodal_personality/training/baseline.py 负责训练、评估和 checkpoint 加载，app/services/multimodal_personality_service.py 负责在线任务和真实推理接入。前端方面，Assessment.vue 对应测评流程，BigFiveReport.vue 对应大五报告，Chat.vue 对应报告上下文咨询。

这些文件名看起来只是工程细节，但它们能减少论文中的空泛描述。比如写“系统实现了大五人格报告”不如说明报告页如何判断 is_real_result，写“系统支持断点续答”不如说明 resume-session 返回 current_stage、submitted_stages、answers 和 questions。后续答辩时，也可以直接根据这些文件演示功能来源。
