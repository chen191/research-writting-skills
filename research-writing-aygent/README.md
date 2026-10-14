# research-writing-aygent

当前 Aygent 科研前台使用的独立写作 Skill，按用户要求从线上已挂载版本完整导出。它与原有 `research-writing-skill` 并列保存，不覆盖原包，也不自动同步或更新线上服务。

## 文件与来源

- `SKILL.md`：Aygent 适配后的 Skill 入口。
- `references/aygent-workflow.md`：任务目录、冻结需求、来源台账、审查和交付契约。
- `scripts/paper.py`、`scripts/paper_result.py`：现有 PDF 服务及前台结果文件的工作区桥接。
- `references/paper-writing/`：保留的学术写作方法参考。
- `upstream-SKILL.md`、`source-manifest.json`、`LICENSE`：原始入口、上游来源与 MIT 许可。
- `ONLINE_EXPORT.json`：当前线上内容 ID 及 27 个运行文件的 SHA-256、大小清单；本文档与该清单是仓库交接附件，不属于线上运行包。

写作方法来自 `zLanqing/codex-claude-academic-skills`。具体来源提交及文件级归属以原始 `source-manifest.json` 为准；上游原文、许可和来源记录保持原始字节；运行文件与当前线上版本一致，不作换行或格式转换。

## 改造范围

适配中文论文/综述任务，从冻结用户需求、核验来源和论证规划，到机械检查、真实独立审查、PDF 逐页检查与 `portal-result.json` 交付。不生成假审查、虚构数据或学术认证。

## 运行依赖与边界

这不是下载后在任意电脑上即可完整运行的离线写作程序：

1. 宿主需提供实际的网页检索、工作区文件/命令、独立子 Thread 与图像阅读能力。
2. `scripts/service-endpoints.json` 保留线上 PDF 服务的私网地址；本地环境必须能访问相应服务，或在另行授权的部署中配置对应地址。
3. 前台任务需要真实任务 UUID 和 `/workspace/paper-<UUID>` 目录。不能借用其他用户或历史任务的文件。
4. 不包含云平台密钥、用户账号、需求记录、稿件、任务数据库或前台部署代码。下载本目录不等于获得平台或服务访问权限。
5. 最初导出未修改线上服务；本次维护仅清理 Skill 运行说明中的过时表述，不改变写作流程、脚本、核验要求、Agent 绑定、模型配置或已有任务，也未发起论文生成。

## 校验

对 `ONLINE_EXPORT.json` 中每个文件按原始字节计算 SHA-256，应与清单一致。已完成 27/27 文件核对、Python AST 语法检查、JSON 解析和敏感内容检查；未将这些静态校验描述为实际论文生成验收。
