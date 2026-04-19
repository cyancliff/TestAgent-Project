import asyncio
import concurrent.futures
import os
import queue

from openai import OpenAI

# 评分标准（注入到辩论专家 prompt 中）
SCORING_STANDARD = """
【评分标准参考】测评采用 1-5 分李克特量表，四个维度各 10 题，单维度基础满分 50 分。
等级划分：
- 偏低（10-23 分，潜伏特质）
- 中等（24-37 分，情境特质）
- 偏高（38-50 分，显性主导特质）
前两题存在加权调节机制（+2 分）。对外展示以 50 分为封顶。请在分析中结合用户的维度得分等级进行解读。
"""


def _retrieve_rag_evidence(user_data_context: str) -> str:
    """同步包装：从 ATMR 知识库中检索与用户数据相关的证据。"""
    try:
        from app.services.rag_service import retrieve_evidence_for_debate

        traits_keywords: list[str] = []
        for trait in ["A", "T", "M", "R"]:
            if f'"{trait}"' in user_data_context or f"模块 {trait}" in user_data_context:
                traits_keywords.append(trait)
        user_traits = ", ".join(traits_keywords) if traits_keywords else "ATMR"

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                evidence = pool.submit(asyncio.run, retrieve_evidence_for_debate(user_traits)).result(timeout=30)
        else:
            evidence = asyncio.run(retrieve_evidence_for_debate(user_traits))

        if evidence:
            print(f"[辩论服务] RAG 检索到 {len(evidence)} 字符的证据")
        return evidence or ""
    except Exception as e:
        print(f"[辩论服务] RAG 检索失败（不影响辩论）: {e}")
        return ""


def _build_client_config(model: str, api_key_env: str, base_url: str) -> dict:
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"未配置 {api_key_env}")
    return {"model": model, "api_key": api_key, "base_url": base_url}


def _call_agent(agent_name: str, config: dict, system_prompt: str, user_prompt: str, *, temperature: float, max_tokens: int) -> str:
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"], timeout=120.0)
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError(f"{agent_name} 返回内容为空")
    return content


def _call_agent_with_fallback(
    agent_name: str,
    primary_config: dict,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float,
    max_tokens: int,
    fallback_config: dict | None = None,
) -> str:
    client = OpenAI(
        api_key=primary_config["api_key"],
        base_url=primary_config["base_url"],
        timeout=120.0,
    )
    try:
        response = client.chat.completions.create(
            model=primary_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        message = response.choices[0].message
        content = (message.content or "").strip()
        if content:
            return content

        reasoning = (getattr(message, "reasoning_content", None) or "").strip()
        if reasoning and fallback_config is not None:
            print(f"[辩论服务] {agent_name} 主模型仅返回 reasoning，改用备用模型整理正式输出")
            formatter_system = "请将给定分析草稿整理为正式结论。只输出最终观点，不要暴露推理过程。"
            formatter_user = f"""请将以下分析草稿整理成一段结构清晰、专业但简洁的正式输出：

{reasoning[:12000]}
"""
            return _call_agent(
                agent_name,
                fallback_config,
                formatter_system,
                formatter_user,
                temperature=0.2,
                max_tokens=max_tokens,
            )
        raise RuntimeError(f"{agent_name} 返回内容为空")
    except Exception:
        if fallback_config is None:
            raise
        print(f"[辩论服务] {agent_name} 主模型失败，切换到备用模型")
        return _call_agent(
            agent_name,
            fallback_config,
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def _queue_agent_message(message_queue: queue.Queue, agent: str, content: str) -> None:
    message_queue.put({"agent": agent, "content": content, "type": "message"})


def _execute_parallel_round(message_queue: queue.Queue, round_specs: list[dict]) -> dict[str, str]:
    if not round_specs:
        return {}

    results: dict[str, str] = {}
    errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(round_specs)) as executor:
        future_map = {
            executor.submit(spec["callable"]): spec
            for spec in round_specs
        }
        for future in concurrent.futures.as_completed(future_map):
            spec = future_map[future]
            try:
                results[spec["agent"]] = future.result()
            except Exception as exc:
                errors.append(f"{spec['agent']}: {exc}")

    if errors:
        raise RuntimeError("并发辩论执行失败：" + "; ".join(errors))

    ordered_results: dict[str, str] = {}
    for spec in round_specs:
        content = results[spec["agent"]]
        _queue_agent_message(message_queue, spec["agent"], content)
        ordered_results[spec["agent"]] = content

    return ordered_results


def run_debate_streaming(user_data_context: str, message_queue: queue.Queue):
    """
    多智能体辩论逻辑，通过 message_queue 实时推送每条消息。
    消息格式: {"agent": str, "content": str, "type": "message"|"done"|"error"}
    """
    try:
        print(f"[辩论服务] 开始辩论，用户数据长度: {len(user_data_context)}")

        zhipu_cfg = _build_client_config(
            "glm-4.5-air",
            "ZHIPU_API_KEY",
            "https://open.bigmodel.cn/api/paas/v4",
        )
        qwen_cfg = _build_client_config(
            "qwen3.5-flash-2026-02-23",
            "DASHSCOPE_API_KEY",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        deepseek_cfg = _build_client_config(
            "deepseek-chat",
            "DEEPSEEK_API_KEY",
            "https://api.deepseek.com/v1",
        )

        print(
            f"[辩论服务] API 密钥检查 - "
            f"DeepSeek: {'已设置' if os.environ.get('DEEPSEEK_API_KEY') else '未设置'}, "
            f"DashScope: {'已设置' if os.environ.get('DASHSCOPE_API_KEY') else '未设置'}, "
            f"Zhipu: {'已设置' if os.environ.get('ZHIPU_API_KEY') else '未设置'}"
        )

        proponent_round1_system = (
            "你是综合辩论中的正方心理学专家。"
            "你拿到的是四个模块的裁判总结，而不是原始答题记录。"
            "请从结构优势、积极潜力、可迁移能力和内在一致性的角度做第一轮综合发言。"
            f"{SCORING_STANDARD}"
        )
        proponent_round1_user = f"""以下是 ATMR 四个模块的分层辩论裁判总结，请独立完成第一轮正方发言：

{user_data_context}

请完成：
1. 提炼最值得肯定的整体人格结构与跨模块协同
2. 指出哪些模块最能形成稳定优势与发展杠杆
3. 对风险保持克制，但不要回避结构性短板

请输出一段结构清晰、专业但简洁的分析。"""

        opponent_round1_system = (
            "你是综合辩论中的反方风控专家。"
            "你拿到的是四个模块的裁判总结，而不是原始答题记录。"
            "请从结构性风险、情境脆弱点、过度美化的可能和需要谨慎解释的部分做第一轮综合发言。"
            f"{SCORING_STANDARD}"
        )
        opponent_round1_user = f"""以下是 ATMR 四个模块的分层辩论裁判总结，请独立完成第一轮反方发言：

{user_data_context}

请完成：
1. 提炼最需要谨慎对待的跨模块风险与张力
2. 说明哪些优势可能高度依赖情境，不能直接外推
3. 指出最值得在第二轮继续深挖的问题

请输出一段结构清晰、专业但简洁的分析。"""

        round1_results = _execute_parallel_round(
            message_queue,
            [
                {
                    "agent": "Proponent_GLM_R1",
                    "callable": lambda: _call_agent_with_fallback(
                        "Proponent_GLM_R1",
                        zhipu_cfg,
                        proponent_round1_system,
                        proponent_round1_user,
                        temperature=0.7,
                        max_tokens=650,
                        fallback_config=deepseek_cfg,
                    ),
                },
                {
                    "agent": "Opponent_Qwen_R1",
                    "callable": lambda: _call_agent_with_fallback(
                        "Opponent_Qwen_R1",
                        qwen_cfg,
                        opponent_round1_system,
                        opponent_round1_user,
                        temperature=0.7,
                        max_tokens=650,
                        fallback_config=deepseek_cfg,
                    ),
                },
            ],
        )
        proponent_round1 = round1_results["Proponent_GLM_R1"]
        opponent_round1 = round1_results["Opponent_Qwen_R1"]
        print(
            f"[辩论服务] 第一轮完成，正方长度: {len(proponent_round1)}，"
            f"反方长度: {len(opponent_round1)}"
        )

        judge_guidance_system = f"""你是中场裁判，负责在综合辩论第一轮后提出深入且有启发性的建议。{SCORING_STANDARD}
请不要直接给出最终结论，而是：
1. 指出双方目前最关键的分歧与共识
2. 提出 1-2 个能推动第二轮深化的追问或观察角度
3. 这些建议要具体到 ATMR 四个模块之间的联动，而不是泛泛而谈
输出要求：直接输出建议正文，不要写客套话。"""
        judge_guidance_user = f"""请阅读以下第一轮发言，并提出第二轮需要继续深挖的建议：

【模块层裁判总结】
{user_data_context}

【正方第一轮】
{proponent_round1}

【反方第一轮】
{opponent_round1}
"""

        judge_guidance = _call_agent(
            "Judge_DeepSeek_Guidance",
            deepseek_cfg,
            judge_guidance_system,
            judge_guidance_user,
            temperature=0.4,
            max_tokens=600,
        )
        _queue_agent_message(message_queue, "Judge_DeepSeek_Guidance", judge_guidance)
        print(f"[辩论服务] 中场建议完成，长度: {len(judge_guidance)}")

        proponent_round2_system = (
            "你是综合辩论中的正方心理学专家。"
            "请在第二轮中正面回应裁判提出的深化建议，"
            "补足第一轮中被忽略的边界条件，同时继续说明该用户最可能形成的成长路径。"
            f"{SCORING_STANDARD}"
        )
        proponent_round2_user = f"""请基于以下材料完成第二轮正方回应：

【模块层裁判总结】
{user_data_context}

【正方第一轮】
{proponent_round1}

【反方第一轮】
{opponent_round1}

【裁判中场建议】
{judge_guidance}

输出要求：
1. 逐步回应裁判提出的关键追问
2. 说明哪些风险经过重新审视后仍可被优势抵消，哪些不能
3. 给出更成熟、更有边界感的正方判断

请输出一段结构清晰、专业但简洁的分析。"""

        opponent_round2_system = (
            "你是综合辩论中的反方风控专家。"
            "请在第二轮中正面回应裁判提出的深化建议，"
            "把风险分析推进到更深一层，但不要为了反对而反对。"
            f"{SCORING_STANDARD}"
        )
        opponent_round2_user = f"""请基于以下材料完成第二轮反方回应：

【模块层裁判总结】
{user_data_context}

【正方第一轮】
{proponent_round1}

【反方第一轮】
{opponent_round1}

【裁判中场建议】
{judge_guidance}

输出要求：
1. 逐步回应裁判提出的关键追问
2. 指出哪些潜在风险在第二轮后仍未被充分化解
3. 给出更精准、更有证据边界的反方判断

请输出一段结构清晰、专业但简洁的分析。"""

        round2_results = _execute_parallel_round(
            message_queue,
            [
                {
                    "agent": "Proponent_GLM_R2",
                    "callable": lambda: _call_agent_with_fallback(
                        "Proponent_GLM_R2",
                        zhipu_cfg,
                        proponent_round2_system,
                        proponent_round2_user,
                        temperature=0.6,
                        max_tokens=650,
                        fallback_config=deepseek_cfg,
                    ),
                },
                {
                    "agent": "Opponent_Qwen_R2",
                    "callable": lambda: _call_agent_with_fallback(
                        "Opponent_Qwen_R2",
                        qwen_cfg,
                        opponent_round2_system,
                        opponent_round2_user,
                        temperature=0.6,
                        max_tokens=650,
                        fallback_config=deepseek_cfg,
                    ),
                },
            ],
        )
        proponent_round2 = round2_results["Proponent_GLM_R2"]
        opponent_round2 = round2_results["Opponent_Qwen_R2"]
        print(
            f"[辩论服务] 第二轮完成，正方长度: {len(proponent_round2)}，"
            f"反方长度: {len(opponent_round2)}"
        )

        judge_final_system = f"""你是主裁决官，负责综合两轮辩论并最终输出 ATMR 综合评估报告。{SCORING_STANDARD}
【强制规则】
你必须直接输出一份结构化、专业的心理画像报告，包含以下板块：
1. 整体画像
2. 认知特征
3. 情感模式
4. 行为风格
5. 潜力与风险
6. 深入建议

补充要求：
- 不要写“感谢各位专家”之类的客套话。
- 不要提及“正方/反方/两位专家/第一轮/第二轮”等元信息。
- 结论要体现跨模块整合，而不是简单拼接四个模块摘要。
- 必须在正文最后一行输出 TERMINATE。"""
        judge_final_user = f"""请综合以下材料，输出最终评估报告：

【模块层裁判总结】
{user_data_context}

【正方第一轮】
{proponent_round1}

【反方第一轮】
{opponent_round1}

【裁判中场建议】
{judge_guidance}

【正方第二轮】
{proponent_round2}

【反方第二轮】
{opponent_round2}
"""

        judge_content = _call_agent(
            "Judge_DeepSeek_Final",
            deepseek_cfg,
            judge_final_system,
            judge_final_user,
            temperature=0.5,
            max_tokens=1400,
        )
        _queue_agent_message(message_queue, "Judge_DeepSeek_Final", judge_content)
        print(f"[辩论服务] 最终裁判完成，长度: {len(judge_content)}")

        final_report = judge_content.replace("TERMINATE", "").strip()
        message_queue.put({"agent": "system", "content": final_report, "type": "done"})
        print("[辩论服务] 完成消息已放入队列")

    except Exception as e:
        print(f"[辩论服务] 发生异常: {e}")
        import traceback

        traceback.print_exc()
        message_queue.put({"agent": "system", "content": str(e), "type": "error"})
