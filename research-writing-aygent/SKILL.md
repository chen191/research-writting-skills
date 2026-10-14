---
name: research-writing-aygent
description: 独立的中文科研论文与综述写作流程；从用户需求、真实来源和论证规划到初稿、独立审查、修订及当前科研前台的PDF交付。用于新论文、章节撰写和稿件修订，不承担实验执行或未经授权的平台维护。
---

# Research Writing · Aygent

本 Skill 独立运行。写作方法来自 `zLanqing/codex-claude-academic-skills` 的 research-writing-skill；原文和 MIT 许可见本包的 `upstream-SKILL.md`、`LICENSE`、`source-manifest.json`。原文只作方法参考，不赋予其它 Skill、工具或权限。

## 基本约定

- 默认中文学术表达，保留英文题名、术语、公式、变量和真实题录。优先准确、具体、有论证的段落，不写泛泛的宣传文字或生成流程流水账。
- 区分来源已有结果、用户提供数据、合理推断和建议；不编造实验、性能、DOI、作者、机构、身份或结果。不将搜索片段称为论文摘要/全文。
- 原指南偏系统与网络论文，属于可选写作方法，不是所有学科的硬模板。综述不虚构“我们提出的新方法”、原创实验或结果预告；用户模板与真实研究类型优先。没有测量数据时，不为了满足 rhetorical move 填数字。
- 每篇只访问消息指定的 `/workspace/paper-<任务UUID>`；用户主题、正文目标、文献最低数量、补充要求和模板先冻结。不读取、借用其它用户/旧任务的正文、审查或 PDF。
- 只用当前宿主实际提供的原生搜索/网页、文件/命令、独立子 Thread 和图像阅读工具。web_search 是能力统称；若提供 `web.run`，用其 search_query/open。不因工具名称不同误判不存在，不安装替代服务。

## 流程

先读 [Aygent 工作流与文件契约](references/aygent-workflow.md)，用本 Skill 的真实挂载路径执行 `scripts/paper.py`，不要猜另一个 Skill 的路径。

1. **明确需求与论证规划**。保存并 freeze 用户需求；判断是综述、原创研究还是修订。有关键资料缺失且无法从已授权来源补齐时，向用户提最少必要问题。建立 `outline.md`：研究问题、章节要回答的问题、可用证据、限制。题目不清晰时读 [brainstorming](references/paper-writing/brainstorming_guide.md)。
2. **真实检索与来源台账**。围绕章节问题少量多轮搜索，打开原始论文页/官方资料；够用即停止，缺什么补什么，不为了凑文献使用不相关条目。在 `sources.json` 保存可核验题录、URL、实际读取范围、定位和要点；`evidence_level` 仅能是实际获得的 abstract/fulltext/user_provided。摘要只支持摘要中的论断。必要经典文献可保留，不把更新时间误当首发年。
3. **起草与结构化表达**。正文写入 `paper.md`，参考文献另列 `[S1]` 等独立段落；正文使用同样的 `[S1]` 引用。不要求每段强行引用，但外部事实/数据/研究结论必须有支持。引言按 [introduction](references/paper-writing/section_rhetorical_moves/introduction.md) 调整适合本论文的 moves；相关研究按 [related_work](references/paper-writing/section_rhetorical_moves/related_work.md) 比较问题、假设和局限，不逐篇罗列。只有真实原创研究才按 [design](references/paper-writing/section_rhetorical_moves/design.md)、[evaluation](references/paper-writing/section_rhetorical_moves/evaluation.md) 写方法/实验，缺数据则明确限制。正文达到用户目标，不用摘要、表格或重复段落充数。
4. **检查与真实独立审查**。运行 `check`，由现有编译服务执行唯一的机械检查；脚本只使用返回的正文计数。再运行 `review-input`，创建一个全新、fresh/sync 的独立审查子 Thread，完整阅读稿件、需求、来源和机械报告。审查事实/引用支持、章节论证、重复/过度声称以及来源指南的适用性。审查者自己写 `review.json`，最终原样返回 JSON。作者从真实 `create_thread` 返回保存 `native-review-return.json`，用 `accept-review` 核对交接、身份字段与输入哈希；不能代写 PASS、自造 ID 或用角色扮演代替独立审查。最多两轮针对阻断的修改，每次修改重新 check 并用新的独立审查者复核；仍不合格则如实停止，不循环碰运气。
5. **PDF 与前台交付**。只有当前稿机械与独立审查通过，获得本任务 PDF 编译授权后才能 `render`。沿用用户冻结的模板；现有服务不支持外嵌图片，本 Skill 的 figure 指南只用于规划，不改长期服务或装图像生成器。运行 `preview` 获取所有页面，用真实图像阅读逐页检查乱码、裁切、空白、表格/引用与标题排版；保存绑定当前 PDF 的 `visual-review.json`。最后 `publish` 创建本任务的 `portal-result.json`，由正式前台按 Thread 文件 API 校验下载。禁止手写 ready、假造四项 checks、借旧 PDF、调用已取消的 submit_delivery。

## 按需参考

- 引言/相关工作自检：[intro_questions](references/paper-writing/writing_checklists/intro_questions.md)、[related_work_questions](references/paper-writing/writing_checklists/related_work_questions.md)。
- 原创设计/评估自检：[design_questions](references/paper-writing/writing_checklists/design_questions.md)、[evaluation_questions](references/paper-writing/writing_checklists/evaluation_questions.md)。
- 润色与压缩：[editorial_principles](references/paper-writing/author_profile/editorial_principles.md)、[compression_patterns](references/paper-writing/author_profile/compression_patterns.md)。其它 author_profile 文件保留用于需要时参考，不模仿特定作者身份，不当作真实来源或学术认证。
- 图表规划：[figure_synthesis_guide](references/paper-writing/figure_synthesis_guide.md)、[figure_spec_template](references/paper-writing/figure_templates/figure_spec_template.md)。工具/绘图/实验请求需要另外的实际能力与授权，本文包不会自动执行。

## 完成边界

最终简要说明交付文件、来源范围、仍需人工核对事项。真实任务未完成或缺证据时留下 `blocked.json` 并说明原因；Run completed、机械通过、模型 PASS 和学术认证不是同一件事。首次未知编译请求不自动重发。禁止修改后台、模型连接/默认、长期服务或其它任务。
