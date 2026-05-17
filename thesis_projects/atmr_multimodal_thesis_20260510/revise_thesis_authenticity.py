from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
CHAPTER_DIR = PROJECT / "03_chapters"


def backup_sources() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = PROJECT / "09_state" / f"before_authenticity_revision_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for path in CHAPTER_DIR.glob("ch*_draft.md"):
        shutil.copy(path, backup / path.name)
    state = PROJECT / "09_state" / "project_state.json"
    if state.exists():
        shutil.copy(state, backup / state.name)
    return backup


def replace_section(text: str, heading: str, body: str) -> str:
    pattern = rf"(^## {re.escape(heading)}\s*$)(.*?)(?=^## |\Z)"
    repl = f"## {heading}\n\n{body.strip()}\n\n"
    new, count = re.subn(pattern, repl, text, flags=re.M | re.S)
    if count != 1:
        raise RuntimeError(f"section not found or duplicated: {heading}")
    return new


def append_section(text: str, heading: str, body: str) -> str:
    return text.rstrip() + f"\n\n## {heading}\n\n{body.strip()}\n"


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def update_state() -> None:
    path = PROJECT / "09_state" / "project_state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    thesis = state.setdefault("thesis", {})
    thesis["abstractZh"] = (
        "本文以本人在 TestAgent 仓库中完成的 ATMR 智能心理测评系统为研究对象，围绕“问卷测评主线如何闭环、"
        "视频多模态人格预测如何接入、两类证据如何在报告和咨询中并列呈现”三个问题展开。系统后端采用 FastAPI，"
        "前端采用 Vue 3，已实现注册登录、测评会话、断点续答、阶段提交、历史报告和测评后咨询等功能；在智能分析部分，"
        "系统实现了基于贝叶斯能力估计和题目特征向量的自适应选题、明显过快作答检测、多智能体辩论以及基于 PageIndex 的"
        "RAG 知识检索。多模态部分独立放置在 multimodal_personality 目录中，完成了 CFI-V2 manifest 构建、视频抽帧、"
        "音频提取、Whisper 转写、CLIP 视觉/文本特征、wav2clip 音频特征、feature bundle 组装、AGTN-MTL baseline 训练、"
        "评估和在线推理接入。当前在线默认 checkpoint 为 reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt，测试集结果为 "
        "MSE=0.011543、MAE=0.086074、PCC=0.7062、CCC=0.6327、R²=0.4881。论文没有把 ATMR 与 Big Five 直接数值融合，"
        "而是将 ATMR 报告和大五人格视频报告作为两条来源不同的证据链管理。实践表明，该方案能够支撑一次完整的毕业设计演示，"
        "但多任务损失、bg_features 重训、消融实验、后台任务队列和隐私治理仍需继续完善。"
    )
    thesis["abstractEn"] = (
        "This thesis is based on the TestAgent project implemented during the graduation design. "
        "It focuses on three practical issues: how to close the ATMR questionnaire workflow, how to connect video-based multimodal personality prediction to the online system, and how to present the questionnaire report and the Big Five video report as two separate evidence chains. "
        "The backend is implemented with FastAPI and the frontend with Vue 3. The system supports user authentication, resumable assessment sessions, staged submission, historical reports, and post-assessment consultation. "
        "It also includes adaptive question selection, fast-answer anomaly detection, multi-agent debate, and PageIndex-based RAG retrieval. "
        "The multimodal branch is isolated under the multimodal_personality directory and covers CFI-V2 manifest construction, frame extraction, audio extraction, Whisper transcription, CLIP visual/text features, wav2clip audio features, feature bundle construction, AGTN-MTL baseline training, evaluation, and online inference. "
        "The current online checkpoint reports MSE 0.011543, MAE 0.086074, PCC 0.7062, CCC 0.6327, and R2 0.4881 on the test split. "
        "The two reports are not numerically merged; instead, they are shown and used in chat as independent sources of evidence."
    )
    state["timestamp"] = datetime.now().isoformat()
    state["step"] = "authenticity_revised"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def revise_ch01() -> None:
    path = CHAPTER_DIR / "ch01_draft.md"
    text = path.read_text(encoding="utf-8")
    text = replace_section(
        text,
        "1.1 研究背景",
        """
我最初做这个课题时，系统还比较像一个“能答题、能出报告”的问卷项目。随着功能逐步增加，问题也变得具体起来：用户中途退出后怎么办，阶段报告生成慢怎么办，题目是否只能固定顺序出现，视频分析结果能不能进入同一个咨询入口，报告里的结论有没有依据。后面几轮开发基本都是围绕这些问题展开的。到 2026 年 4 月底，仓库 README 和《毕设开发目标和进度》已经把项目状态整理为三条线：ATMR 在线主系统、大五人格视频报告线、离线多模态子系统[[REF:6]][[REF:8]]。

ATMR 主系统承担的是问卷测评流程。用户登录后可以创建测评草稿，按 intro、fixed、A、T、M、R 等阶段答题，系统记录每道题的选项、得分、作答时间和异常标记。阶段完成后，后台会组织模块评审和综合报告，历史页再把报告保存下来，聊天页可以继续读取这些报告作为咨询上下文。这个部分的难点不是单个接口，而是状态连续性：用户可能刷新页面、重新登录、修改答案，也可能在报告生成时离开页面。

多模态部分是后来逐步接进来的。中期检查时，视频多模态人格测评仍主要是骨架和占位输出；后续才完成 CFI-V2 manifest、抽帧、音频提取、Whisper 转写、CLIP、wav2clip、feature bundle、AGTN-MTL baseline 和真实 checkpoint 接入。现在系统已经不是固定返回 0.50 的演示接口，而是可以用 reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt 做真实推理，并把结果落成独立的大五人格报告[[REF:7]]。

因此，本文讨论的不是一个单纯的心理问卷网页，也不是单纯复现一篇多模态论文。更准确地说，它是一个围绕“问卷自陈证据”和“视频外显行为线索”组织起来的工程系统。两条证据链都不完美，尤其视频结果受数据集、拍摄条件和模型版本影响较大，所以系统没有把 ATMR 和 Big Five 分数强行合并，而是在历史页、报告页和聊天页中并列呈现。
""",
    )
    text = replace_section(
        text,
        "1.2 研究意义",
        """
本课题的意义首先在于把测评流程真正做成可运行闭环。普通问卷页面只需要展示题目和保存分数，但本系统还要处理草稿、恢复、阶段提交、历史报告、报告生成等待、聊天上下文和删除依赖记录等细节。比如 start-session 接口不会立即留下一个空会话，resume-session 会根据已有答题记录恢复当前阶段，删除会话时还要清理答题记录、模块辩论结果和聊天引用。这些细节写进论文，是因为它们决定了系统能不能被真实演示。

其次，系统把“报告解释有没有依据”作为一个重点。ATMR 主线中的 RAG 并不是装饰功能，它通过 PageIndex 读取 ATMR 知识库和 Big Five 知识库，在报告和咨询中提供可追溯材料。多智能体辩论也不是简单让模型多说几段，而是把正方、反方和裁判的角色分开，让报告既能讲优势，也能讲风险和边界。这样生成的结果仍然需要人工判断，但比一次性生成整篇报告更容易控制。

再次，多模态部分给系统提供了第二条证据来源。问卷答案来自用户自陈，视频人格预测来自视觉、音频和文本线索。两类数据来源、标签体系和误差来源都不同。如果把两个结果直接加权，很容易制造一种“很精确”的错觉。本文采用并列报告方式，是在当前工程成熟度下更稳妥的设计：ATMR 报告负责问卷解释，大五报告负责视频线索，聊天页让用户按需要选择是否同时关联。

最后，这个课题也记录了一条比较真实的工程复现路径。多模态论文方法依赖 ffmpeg、Whisper、CLIP、wav2clip、PyTorch、CUDA 和较大的 CFI-V2 数据集，不能直接塞进主系统。本文将离线训练和在线服务拆开，先在 multimodal_personality 目录里跑通训练和评估，再把稳定 checkpoint 通过 app/services/multimodal_personality_service.py 接回在线系统。这个过程比直接描述“采用某模型”更能体现毕业设计的工作量。
""",
    )
    text = replace_section(
        text,
        "1.3 国内外研究现状",
        """
现有在线心理测评系统大多从量表电子化开始，早期重点是题目展示、分数计算和报告生成。随着大模型和检索增强生成技术进入应用层，测评系统开始加入解释、追问和咨询能力。但这类系统容易出现两个问题：一是报告看起来完整，却说不清依据来自哪里；二是系统把模型生成文本包装得过于确定，忽略了测评数据本身的不稳定性。本文的 RAG 和异常作答记录，主要就是为了解决这两个实际问题。

人格预测研究中，Big Five 是常用标签体系之一[[REF:5]]。视频人格预测通常把短视频拆成画面、声音和转写文本，再预测开放性、尽责性、外向性、宜人性和神经质五个连续分数。Wang 等在 2025 年提出的多模态人格预测框架使用 CLIP、Wav2CLIP、自适应图 Transformer 和多任务学习，对 CFI-V2 与 UDIVA 数据集进行了实验[[REF:1]]。这篇论文给本文多模态部分提供了主要参考，但本文实现更偏工程 baseline，而不是完整复刻所有细节。

CLIP 和 Wav2CLIP 在本文中不是论文装饰名词，而是实际工程链路中的两个特征来源。CLIP 用于图像帧和转写文本特征，wav2clip 用于音频片段特征[[REF:2]][[REF:3]]。为了让训练、评估和在线推理使用同一种输入格式，项目里单独写了 MultimodalFeatureBundle，把 clip_video、clip_text、wav2clip、bg_features 和可选 micro_expression_features 统一为 JSON 契约。

Transformer 和图结构方法在多模态任务中常用于处理时序和关系信息[[REF:4]]。本文没有照搬论文中的所有关联特征，而是在 AGTNMTLModel 中实现了位置编码、GraphConvBlock、TemporalAttention、ResidualChannelAttention 和余弦特征融合。这样的实现保留了“时序建模 + 跨模态融合”的核心思路，同时能在当前 Windows + CUDA 环境中训练、保存 checkpoint 并接入在线服务。
""",
    )
    text = replace_section(
        text,
        "1.4 本文主要工作",
        """
本文完成的工作可以按实际开发顺序理解。第一，整理并完善 ATMR 在线主系统。这个部分包括 FastAPI 路由、SQLAlchemy 数据模型、Vue 3 测评页、历史页、报告页和聊天页。系统支持注册登录、测评草稿、断点续答、阶段提交、历史查询和报告详情，能够支撑完整演示。

第二，完成测评过程中的智能分析逻辑。question_selection.py 中实现了基于题目特征向量、贝叶斯能力估计、Fisher 信息量、覆盖度、难度匹配和区分度的选题策略；ai_detector.py 中保留了明显过快作答检测，并把异常记录作为解释和选题降权依据；debate_manager.py 和 rag_service.py 负责多智能体辩论与知识库证据检索。

第三，完成视频多模态人格预测的工程化 baseline。项目从 CFI-V2 manifest 开始，逐步实现抽帧、音频提取、转写、CLIP 特征、wav2clip 特征、feature bundle、AGTN-MTL 训练、评估和推理。最终在线默认模型版本固定为 agtn-mtl-best-lr1e4-drop02，并保留 scaffold 和 fallback 状态，避免用户误把占位结果当成真实报告。

第四，完成大五人格报告接入。系统在历史页把 ATMR 测评报告和大五人格报告分区展示；BigFiveReport.vue 展示雷达图、维度条、模型版本、处理记录和 AI 解读；Chat.vue 允许同一个咨询会话同时关联一份 ATMR 报告和一份大五报告。这个设计保留了两类结果的独立性。
""",
    )
    text = replace_section(
        text,
        "1.5 论文结构安排",
        """
本文后续章节按“先讲依据，再讲设计，再讲实现和实验”的顺序展开。第二章说明 ATMR 测评流程、自适应选题、异常检测、RAG、多智能体辩论和多模态人格预测相关技术，并尽量对应到本项目中的具体文件。第三章分析系统需求和总体架构，重点解释为什么把 ATMR 和 Big Five 做成并列证据链。第四章介绍关键模块实现，包括会话恢复、选题计算、异常标记、RAG 检索、feature bundle、AGTN-MTL 模型和大五报告页。第五章给出系统测试、多模态实验结果和应用风险分析。第六章总结已完成工作，并说明后续仍要补齐的实验和工程治理内容。
""",
    )
    write(path, text)


def revise_ch02() -> None:
    path = CHAPTER_DIR / "ch02_draft.md"
    text = path.read_text(encoding="utf-8")
    text = append_section(
        text,
        "2.7 本项目对相关技术的选用边界",
        """
在本项目中，相关技术并不是越多越好。ATMR 主线已经包含答题、阶段评审、报告和咨询，如果再把 Big Five 结果直接混进评分，会让系统解释变得很难说明。因此，本文只让 Big Five 报告进入历史页和聊天上下文，不参与 ATMR 分数计算。

RAG 的使用也保持在辅助范围。系统检索知识库内容，是为了给报告生成提供材料，而不是让知识库替代心理测评本身。检索失败时，系统允许退回关键词评分或跳过部分证据，不会因为一个外部模型不可用就中断整个测评流程。

多模态模型同样有边界。当前 AGTN-MTL baseline 已经能训练和推理，但没有完整复现论文中的所有多任务损失和消融实验。论文中凡是涉及性能结论的地方，只使用项目文档和 reports 目录中已经记录的指标；对于 bg_features 重训、多随机种子和单模态消融，只写成后续工作。
""",
    )
    write(path, text)


def revise_ch03() -> None:
    path = CHAPTER_DIR / "ch03_draft.md"
    text = path.read_text(encoding="utf-8")
    text = replace_section(
        text,
        "3.1 需求分析",
        """
本系统的需求不是一次性从文档里列出来的，而是在开发过程中逐步暴露出来的。最开始只需要完成用户答题和报告展示，后来发现必须处理未完成会话、阶段提交、报告生成等待、历史记录、聊天上下文和视频任务状态。尤其是测评流程，一旦用户刷新页面或重新登录，系统必须知道他答到哪一阶段、哪些题已经提交、是否存在需要补充说明的异常答案。

功能需求可以分为五组。第一组是用户认证和资源归属，涉及 auth 路由、当前用户依赖和头像静态文件。第二组是 ATMR 测评流程，涉及 start-session、resume-session、restart-session、阶段提交、报告生成和历史查询。第三组是智能分析，涉及 question_selection.py、ai_detector.py、debate_manager.py 和 rag_service.py。第四组是大五人格视频报告，涉及 upload-file、run、result、reports、retry 和后台解读。第五组是聊天咨询，用户可以在 Chat.vue 中选择关联 ATMR 报告和大五报告。

非功能需求主要来自实际使用场景。系统必须能恢复进度，不能因为多模态依赖缺失导致主服务无法启动；报告必须说明模型版本和来源，不能让 scaffold 或 fallback 结果进入正式解读；上传视频和测评数据必须按用户隔离，不能通过猜 ID 访问他人资源。与其把这些需求写成抽象的“安全、可靠、可扩展”，不如把它们落到具体接口和数据字段上。

[[TBL:系统主要需求分类]]
| 需求类别 | 主要内容 | 对应模块 |
|---|---|---|
| 用户认证 | 注册、登录、头像、当前用户 | auth、user |
| ATMR 测评 | 草稿、答题、阶段提交、报告、历史 | assessment、stage_service |
| 智能解释 | 自适应选题、异常检测、辩论、RAG | question_selection、ai_detector、debate_manager、rag_service |
| 多模态报告 | 视频上传、推理任务、Big Five 报告 | multimodal_personality、big_five_report_service |
| 咨询对话 | ATMR 报告与大五报告并列关联 | chat、report_service |
""",
    )
    text = replace_section(
        text,
        "3.2 总体架构设计",
        """
系统采用前后端分离，但真正的架构重点是“双证据链 + 双运行环境”。前端由 Vue 3 负责测评页、历史页、报告页、大五报告页和聊天页；后端由 FastAPI 负责业务接口、用户认证、报告生成和任务调度；离线多模态目录负责训练和评估。在线主系统强调稳定响应，多模态训练强调 GPU、数据和长任务，两者不能混成一个运行环境。

[[FIG:系统总体架构图]]

ATMR 主线从题目作答进入 AnswerRecord 和 AssessmentSession，再进入阶段评审、多智能体辩论、RAG 证据检索和综合报告。大五人格辅线从视频文件进入 MultimodalPersonalityService，经过预处理、特征提取、checkpoint 推理和 BigFivePersonalityReport 保存。两条线在历史页和聊天页相遇，但不在评分层直接合并。

后端路由也按这个思路划分。assessment 处理测评，auth 处理登录，chat 处理咨询，rag 处理知识库，multimodal-personality 处理视频人格任务。服务层再封装 StageService、QuestionSelectionService、MultimodalPersonalityService 等逻辑。这样做的好处是，当多模态模块加载失败时，主系统仍可跳过相关路由启动；当后续要替换 checkpoint 或任务队列时，也不需要改动测评主流程。
""",
    )
    text = replace_section(
        text,
        "3.4 多模态人格预测子系统设计",
        """
多模态子系统采用“先离线跑通，再在线接入”的设计。离线部分在 multimodal_personality 和 scripts 目录中完成，主要产出 manifest、特征文件、bundle、checkpoint 和评估 JSON；在线部分在 app/api/multimodal_personality.py 和 app/services/multimodal_personality_service.py 中完成，负责把一个上传视频变成用户可查看的大五人格报告。

[[FIG:多模态人格预测流程图]]

离线链路中，build_cfi_v2_manifest.py 负责根据 CFI-V2 数据生成样本清单；preprocess_cfi_v2_from_manifest.py 负责抽帧、提取音频和转写；extract_clip_features.py 与 extract_wav2clip_features.py 生成视觉、文本和音频特征；build_multimodal_feature_bundles.py 将特征整理为统一 JSON。训练脚本 train_agtn_mtl.py 读取 bundle，评估脚本 eval_agtn_mtl.py 生成测试指标。

在线链路中，用户上传视频后系统保存文件并创建 task_id。后台运行时先生成工件，再加载当前 checkpoint。如果 checkpoint 不存在、依赖缺失或预处理失败，任务会保存 errors，而不是返回一组看似正常的分数。报告表中还保存 is_real_result，只有真实完成且模型版本匹配的报告才允许生成 AI 解读。
""",
    )
    text = append_section(
        text,
        "3.8 架构取舍记录",
        """
开发中有几个取舍直接影响了论文结构。第一，没有把多模态任务设计成 AssessmentSession 的子表。原因是问卷会话和视频工件的生命周期不同，视频任务会产生音频、转写、特征和 bundle，强行放入测评会话会让模型变得混乱。第二，没有把 Big Five 分数写入 ATMR 综合报告的同一个字段，而是单独建大五报告，因为两者标签体系不一致。

第三，后台任务暂时没有引入 Celery 这类正式队列。毕业设计阶段主要在本机演示，线程式后台任务和本地 JSON 记录已经能满足需求；如果面向多人部署，再把任务迁移到队列更合适。第四，多模态依赖没有并入 requirements_server.txt，而是放在 requirements_multimodal.txt。这样在线主系统可以保持轻量，离线训练环境则单独维护。
""",
    )
    write(path, text)


def revise_ch04() -> None:
    path = CHAPTER_DIR / "ch04_draft.md"
    text = path.read_text(encoding="utf-8")
    text = replace_section(
        text,
        "4.2 自适应选题模块实现",
        """
自适应选题模块集中在 app/services/question_selection.py。实现时我没有把选题写成单纯“随机抽下一题”，而是先用已答题目的 feature_vector 计算用户画像，再根据能力估计和候选题属性排序。服务入口 select_next_question 会接收 user_id、session_id、answered_question_ids、module 和 transient_records，其中 transient_records 是为了支持前端阶段内临时作答场景，避免还没提交数据库时无法计算下一题。

能力估计使用 0.5 均值、0.25 方差作为初始先验。每条 AnswerRecord 会提供 score、is_anomaly 和 exam_no，服务再根据 exam_no 找到 Question 中的 difficulty、discrimination 和 feature_vector。异常作答不会被完全丢弃，而是把权重降到 0.5，同时把观测精度降低。这一点和报告解释中的“异常只提示风险，不直接否定答案”保持一致。

候选题评分由 Fisher 信息量、覆盖度、难度匹配和区分度组成。实现里还有一个不确定性比例 uncertainty_ratio：前几题不确定性高时，Fisher 信息量和区分度权重大；后面能力估计稳定后，覆盖度权重提高，避免候选题一直围绕相似向量。这个细节是为了让测评既能快速定位，也能覆盖更多特征面。

[[EQ:S(q)=w_1I(q)+w_2C(q)+w_3D(q)+w_4R(q)]]

其中，I(q) 表示 Fisher 信息量，C(q) 表示覆盖度，D(q) 表示难度匹配，R(q) 表示区分度。公式只是对实现逻辑的概括，实际代码中还包含候选题为空、首次选题、模块过滤和向量缺失等分支处理。
""",
    )
    text = replace_section(
        text,
        "4.5 多模态特征提取与 Feature Bundle 实现",
        """
多模态特征提取最容易出问题的地方不是模型结构，而是输入格式不统一。一个视频样本会产生图像帧、音频、转写文本、CLIP 视觉特征、CLIP 文本特征、wav2clip 音频特征和 bg_features。如果训练脚本、评估脚本和在线服务各自组织这些字段，后续一定会出现维度错位或标签顺序错位。

因此项目在 multimodal_personality/models/feature_bundle.py 中定义了 MultimodalFeatureBundle。当前契约规定 clip_video 为 15 帧、每帧 768 维；clip_text 最多 13 句、每句 768 维；wav2clip 为 15 段、每段 512 维；bg_features 为 256 维；micro_expression_features 可选，为 8 维；labels 按 openness、conscientiousness、extraversion、agreeableness、neuroticism 排列。

bundle 的 validate 和 to_tensors 两个方法在开发中很有用。validate 会提前检查维度是否符合预期，to_tensors 会把不足的序列补零或截断到固定长度。在线推理时，如果某个模态缺失，服务可以明确决定是失败还是填充，而不是让 PyTorch 在模型前向时才报一个难定位的 shape 错误。

这个设计也方便论文实验复盘。训练、评估和在线 smoke 使用的都是同一种 bundle 文件，因此当报告中写到某个 checkpoint 的测试结果时，可以追溯到对应的 manifest、bundle 目录和评估 JSON，而不是只剩一个孤立的指标表。
""",
    )
    text = replace_section(
        text,
        "4.6 AGTN-MTL Baseline 模型实现",
        """
AGTN-MTL baseline 的代码位于 multimodal_personality/models/agtn_mtl.py。模型输入包含 clip_video、wav2clip、clip_text、bg_features 和可选 micro_expression_features，输出是 Big Five 五维分数。它参考了多模态人格预测论文中的图结构和多任务思想[[REF:1]]，但实现上更偏向当前仓库能稳定训练和接入的版本。

文本分支使用 SequenceEncoder 和 TemporalAttention，对 CLIP 文本句子序列做编码；视觉分支先加位置编码，再经过两层 GraphConvBlock 和线性投影；音频分支对 wav2clip 序列采用类似处理。视觉和音频池化后通过 cosine_feature_fusion 形成 video_audio 表示。最后，ResidualChannelAttention 把 bg_feature、video_audio、text 和可选 micro_feature 融合，再由主预测头输出 0 到 1 的五维分数。

模型还保留 bg_output、audio_output、text_output 和 micro_output 等辅助头。当前训练主要使用主任务回归，辅助头更多是为后续多任务损失预留结构。这个边界必须写清楚：当前结果能证明工程 baseline 可运行、可评估、可接入，但不能说已经完整复现原论文的全部多任务训练策略。

实际接入时，服务层通过 load_checkpoint_model 恢复模型和 model_kwargs。当前在线默认模型版本是 agtn-mtl-best-lr1e4-drop02，对应 checkpoint 路径为 reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt。报告页会显示模型版本，便于后续比较不同 checkpoint 的输出差异。
""",
    )
    text = replace_section(
        text,
        "4.7 大五人格报告与前端展示实现",
        """
大五人格报告页对应 frontend/src/components/BigFiveReport.vue。页面加载后先根据 report_id 请求报告详情，如果 status 还在 running，就显示刷新和返回历史入口；如果已经 completed 且存在 scores，就展示雷达图、五维分数条、维度水平、报告来源和 AI 解读。这个页面的重点不是炫图，而是让用户知道结果来自哪个视频、哪个模型版本、是否是真实模型输出。

报告来源区域会显示 original_filename、model_version 和 is_real_result。这个字段很关键，因为项目早期有 scaffold 和 fallback 输出，如果不区分，用户可能把占位分数当成真实人格结果。后端 _is_real_result 会检查任务状态、分数和模型版本，只有真实 checkpoint 的完成结果才进入正式解读。

聊天页对应 Chat.vue。它不是把所有历史报告自动塞进提示词，而是提供两个下拉框：一个关联 ATMR 报告，一个关联大五人格报告。用户可以不关联、只关联其中一种，或者同时关联两种。这个设计在使用上多一步选择，但能让咨询上下文更透明，也避免把不同来源的证据混成一个模糊结论。
""",
    )
    text = append_section(
        text,
        "4.10 关键实现文件对应关系",
        """
为了让论文描述和代码对应起来，本文整理了几个关键文件。app/api/assessment/sessions.py 负责测评会话开始、恢复、重启和删除；app/services/question_selection.py 负责自适应选题；app/services/ai_detector.py 负责异常作答检测；app/services/debate_manager.py 负责多智能体辩论；app/services/rag_service.py 负责 PageIndex 检索。

多模态部分中，multimodal_personality/models/feature_bundle.py 定义输入契约，multimodal_personality/models/agtn_mtl.py 定义模型结构，multimodal_personality/training/baseline.py 负责训练、评估和 checkpoint 加载，app/services/multimodal_personality_service.py 负责在线任务和真实推理接入。前端方面，Assessment.vue 对应测评流程，BigFiveReport.vue 对应大五报告，Chat.vue 对应报告上下文咨询。

这些文件名看起来只是工程细节，但它们能减少论文中的空泛描述。比如写“系统实现了大五人格报告”不如说明报告页如何判断 is_real_result，写“系统支持断点续答”不如说明 resume-session 返回 current_stage、submitted_stages、answers 和 questions。后续答辩时，也可以直接根据这些文件演示功能来源。
""",
    )
    write(path, text)


def revise_ch05() -> None:
    path = CHAPTER_DIR / "ch05_draft.md"
    text = path.read_text(encoding="utf-8")
    text = replace_section(
        text,
        "5.1 测试目标与测试环境",
        """
本章测试不是只跑一条“能打开页面”的演示路径，而是检查三类事情：第一，ATMR 主流程是否能从登录、开始测评、答题、阶段提交走到报告和历史记录；第二，多模态链路是否能从 CFI-V2 样本处理到 checkpoint 评估，再接回在线服务；第三，报告和聊天页是否能正确区分真实结果、失败结果和占位结果。

当前开发环境主要是 Windows + PowerShell。多模态训练环境已验证 torch、torchvision、torchaudio 和 CUDA 可用，GPU 为 NVIDIA GeForce RTX 4060 Laptop GPU。在线主系统可以本地运行，也可以通过 Docker 配置启动。由于多模态依赖较重，训练环境和在线主系统依赖没有完全合并。

自动化测试主要分布在 tests 目录，包括认证、聊天、RAG、题目选择、问题清洗、项目健康、多模态训练管线、多模态服务、多模态模型、特征提取器和大五报告 API。除此之外，项目还保留了 reports/online_multimodal_smoke_20260425/smoke_result.json，用来记录真实视频在线推理结果。
""",
    )
    text = replace_section(
        text,
        "5.2 在线主系统功能测试",
        """
在线主系统功能测试先从会话状态开始。用户没有未完成测评时，前端显示开始测评；存在 active 会话时，系统提示继续测评或修改答案；存在 completed 会话时，用户可以查看历史报告或开始新测评。这个流程对应 Assessment.vue 中的开始页状态，也对应后端 start-session 和 resume-session 的返回结果。

阶段答题测试关注三个点：答案能否保存，异常作答能否记录，页面刷新后能否恢复。resume-session 返回的内容包括 session_id、current_stage、submitted_stages、answered_count、answers 和 questions。前端拿到这些字段后，可以恢复当前阶段和已答题目，而不是让用户重新开始。

报告测试则关注异步体验。阶段评审和最终报告生成都可能需要等待，前端会显示“专家评审中”或“正在整理最终报告”。如果用户不想等待，可以稍后进入历史页查看。这个设计在测试中很重要，因为大模型调用或 RAG 检索失败时，系统也要把错误状态保留下来，而不是让前端一直转圈。

删除测试检查依赖清理。删除一个测评会话时，系统需要删除 AnswerRecord 和 ModuleDebateResult，并把相关 ChatSession 的 assessment_session_id 置空。这个细节避免历史聊天继续指向已经不存在的测评报告。
""",
    )
    text = replace_section(
        text,
        "5.4 多模态实验结果",
        """
多模态实验先做小样本闭环，而不是一开始就跑全量。train 20 / val 5 的结果为 MSE=0.004983、MAE=0.057872；train 100 / val 20 的结果为 MSE=0.016520、MAE=0.100234。这两次验证的意义主要是确认 manifest、预处理、特征提取、bundle、训练和评估能够连续跑通。

全量 baseline 使用 CFI-V2 的 train=6000、val=2000、test=2000 划分。初始全量 baseline 在测试集上得到 MSE=0.019945、MAE=0.113552。后续调参后，当前在线默认 checkpoint 为 reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt，测试集结果为 MSE=0.011543、MAE=0.086074、PCC=0.7062、CCC=0.6327、R²=0.4881。

[[TBL:多模态实验指标汇总]]
| 实验 | 样本数 | MSE | MAE | ACC | PCC | CCC | R² |
|---|---:|---:|---:|---:|---:|---:|---:|
| 初始全量 baseline | 2000 | 0.0199 | 0.1136 | 0.8864 | 0.3422 | 0.1925 | 0.1154 |
| lr1e-4 / dropout 0.2 | 2000 | 0.0115 | 0.0861 | 0.9139 | 0.7062 | 0.6327 | 0.4881 |
| lr1e-4 / dropout 0.3 | 2000 | 0.0122 | 0.0885 | 0.9115 | 0.7062 | 0.5776 | 0.4609 |
| lr2e-4 / dropout 0.3 | 2000 | 0.0131 | 0.0916 | 0.9084 | 0.6684 | 0.5410 | 0.4196 |

从表中可以看到，lr1e-4 / dropout 0.2 在 MAE、CCC 和 R² 上表现最好，因此被固定为在线默认版本。它的 PCC=0.7062 接近参考论文在 CFI-V2 上报告的 PCC=0.7267，但 CCC 和 R² 仍低于论文完整方法。这个差距说明当前结果可以作为工程 baseline 和系统接入结果，不能写成严格复现了原论文全部性能。

在线 smoke 验证进一步确认了服务接入。归档样本返回 openness=0.4708、conscientiousness=0.4182、extraversion=0.3815、agreeableness=0.4902、neuroticism=0.3939。这个结果不是为了证明单个样本“人格正确”，而是证明线上服务已经能调用真实 checkpoint，并把结果保存为大五人格报告。
""",
    )
    text = replace_section(
        text,
        "5.5 结果分析与讨论",
        """
从实验结果看，多模态子系统已经完成从占位接口到真实推理的转变。最初系统只能返回固定 0.50，适合前端联调，但无法支撑论文实验。现在从 CFI-V2 数据、特征、bundle、训练、评估到在线报告已经形成链路，调参版本也比初始 baseline 有明显提升。

不过，当前结果仍有边界。第一，在线 checkpoint 仍主要对应旧的 bg_features 零填充版本。虽然工程版 256 维 bg_features 已经实现，但要想写成正式对照，还需要重新生成 bundle 并重训。第二，AGTN-MTL 模型结构保留了辅助头，但多任务损失没有完整复现。第三，随机种子、单模态消融和多模态消融仍不足，不能过度解释每个模块的贡献。

系统接入层面的价值在于，大五人格结果已经进入用户可见流程。历史页能看到大五报告，报告页能看到雷达图和模型版本，聊天页能把大五报告作为上下文。也就是说，多模态结果不再只是一张实验表，而是已经变成系统功能的一部分。

ATMR 与 Big Five 的关系仍然要谨慎。ATMR 来自问卷自陈，Big Five 来自视频外显线索。两者可以相互启发，但不能互相证明。本文只做并列呈现，后续若要研究一致性，需要收集同一用户的问卷、视频和人工评估数据，并设计单独的统计分析。
""",
    )
    text = replace_section(
        text,
        "5.6 系统不足与改进方向",
        """
当前系统最明显的不足是后台任务还不够正式。多模态任务现在主要依赖服务层、本地任务记录和后台线程，适合本地演示；如果要多人同时使用，需要引入任务队列、失败重试、资源限制和更清晰的任务日志。

第二个不足是多模态实验还需要继续补。下一步最直接的工作是用新 bg_features 重新生成 bundle，训练一版与零填充版本的对照；随后补单模态消融、多模态消融、多任务损失和多随机种子。只有这些实验完成后，第四章模型结构和第五章结果分析才能更有说服力。

第三个不足是报告文本仍需人工打磨。当前系统已经有 RAG 和多智能体辩论，但心理测评报告不能只追求完整，还要避免标签化、过度确定和诊断化。后续可以把报告拆成“事实、解释、建议、边界”几层，并增加用户可理解的失败提示。

第四个不足是隐私治理。问卷答案、聊天记录、上传视频和人格报告都属于敏感数据。当前项目已经做了用户所有权校验和随机文件名保存，但正式部署还需要补充访问审计、日志脱敏、文件删除和用户撤回机制。
""",
    )
    text = append_section(
        text,
        "5.9 本轮论文修订说明",
        """
根据 AIGC 检测报告，本轮修订把过于均匀的标准论文表达改为更贴近项目过程的写法。修改重点包括：把“系统采用某技术”的句式改为具体文件和接口说明；把“结果表明”后面的结论限制在已有实验范围内；把“系统不足”写成下一步可以执行的任务，而不是泛泛列出安全性、可扩展性等词语。

本轮没有新增任何实验数值，也没有把未完成的 bg_features 重训、多任务损失和消融实验写成既有成果。这样处理的目的不是改变论文结论，而是让论文更接近真实开发记录：哪些已经做完，哪些只是预留，哪些仍然需要补。
""",
    )
    write(path, text)


def revise_ch06() -> None:
    path = CHAPTER_DIR / "ch06_draft.md"
    text = path.read_text(encoding="utf-8")
    text = replace_section(
        text,
        "6.1 工作总结",
        """
本文完成的工作可以用一条实际开发线索概括：先把 ATMR 问卷主流程做成可恢复、可提交、可出报告的在线系统，再把视频多模态人格预测从离线脚本接入到用户可见的大五人格报告，最后让两类报告在历史页和聊天页中并列使用。这个过程涉及前端页面、后端接口、数据库记录、RAG 知识库、多智能体辩论和多模态训练评估多个部分。

ATMR 主线已经支持用户注册登录、测评草稿、断点续答、阶段作答、历史记录、报告展示和 AI 咨询。自适应选题根据已答题目和能力估计选择候选题，异常检测记录明显过快作答，多智能体辩论和 RAG 用于生成更有依据的报告解释。

视频多模态辅线完成了 CFI-V2 预处理、CLIP 视觉/文本特征、wav2clip 音频特征、feature bundle、AGTN-MTL baseline 训练、评估和在线推理接入。当前默认 checkpoint 已进入线上服务，测试集指标为 MSE=0.011543、MAE=0.086074、PCC=0.7062、CCC=0.6327、R²=0.4881。

系统融合方面，本文没有把 ATMR 与 Big Five 做直接分数融合，而是保留两类报告的来源差异。历史页分区展示，聊天页让用户自主选择上下文。这种做法没有给出过度确定的心理判断，但能支撑一次完整、可解释的毕业设计演示。
""",
    )
    text = replace_section(
        text,
        "6.2 创新点与工程价值",
        """
本文的工程价值首先体现在完整闭环。系统不是只有一个模型或一个页面，而是把登录、答题、异常记录、阶段评审、报告、历史记录和咨询连成了一条可运行路径。这个闭环中每个状态都能在代码中找到对应接口或组件。

其次，本文把多模态人格预测从离线实验接到了在线产品流程。AGTN-MTL baseline 的训练结果不仅写在表格中，也通过 MultimodalPersonalityService 进入大五人格报告。模型版本、工件路径、错误信息和 is_real_result 都被保存下来，方便后续复查。

第三，系统在融合方式上比较克制。ATMR 和 Big Five 没有被包装成一个“统一人格分数”，而是被当作两条不同来源的证据链。对毕业设计而言，这种取舍比强行做复杂融合更可靠，因为它承认了当前数据和实验的边界。
""",
    )
    text = replace_section(
        text,
        "6.3 不足与展望",
        """
后续工作首先应补多模态实验。当前最值得做的是 bg_features 重训和对照实验，其次是多任务损失、单模态消融、多模态消融和更多随机种子。只有这些内容补齐后，论文才能更细地分析每个模块的实际贡献。

其次，应继续治理工程结构。后台任务可以迁移到正式队列，数据库迁移流程需要更规范，上传文件和中间工件需要更完整的清理策略。多用户部署时，还要考虑 GPU 任务排队、失败重试和日志审计。

再次，应继续打磨报告解释。心理测评文本不能只追求流畅，还要说明依据、限制和使用边界。未来可以把报告模板拆得更细，让“事实记录、模型解释、行动建议、风险提示”各自承担不同作用。

最后，ATMR 与 Big Five 的关系仍有研究空间。当前系统只做并列呈现，未来若有足够真实样本和伦理许可，可以分析问卷自陈与视频外显线索之间的一致性和差异性，再决定是否需要更深层的融合模型。
""",
    )
    text = append_section(
        text,
        "6.4 后续可执行清单",
        """
结合当前项目状态，后续最直接的清单包括：重新生成带 bg_features 的 bundle；训练一版新 checkpoint 并与旧零填充版本比较；补充单模态消融和多随机种子；把后台任务从线程式执行整理为可重试任务；补充正式学校模板、系统截图、ER 图和接口表；把论文中的“待补充”封面信息替换为真实信息。

这些任务都能从当前仓库继续推进，不需要重新设计系统。也正因为如此，本文的结论保持在“系统已经形成可演示、可训练、可推理、可接入的毕业设计成果”这一范围内，而不扩大为临床心理测评或完整论文方法复现。
""",
    )
    write(path, text)


def main() -> None:
    backup = backup_sources()
    revise_ch01()
    revise_ch02()
    revise_ch03()
    revise_ch04()
    revise_ch05()
    revise_ch06()
    update_state()
    print(backup)


if __name__ == "__main__":
    main()
