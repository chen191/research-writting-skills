# research-writing-aygent

当前 Aygent 科研前台使用的独立写作 Skill，按用户要求从线上已挂载版本完整导出。它与原有 `research-writing-skill` 并列保存，不覆盖原包，也不自动同步或更新线上服务。

## 文件与来源

- `SKILL.md`：Aygent 适配后的 Skill 入口。
- `references/aygent-workflow.md`：任务目录、冻结需求、来源台账、审查和交付契约。
- `scripts/paper.py`、`scripts/paper_result.py`：runtime 本地 PDF 编译器及前台结果文件的工作区桥接。
- `scripts/runtime_transport.py`：check/render/preview 的本地进程调用和任务内产物读取；删除会阻断这些步骤，不会回退 HTTP 服务。
- `references/paper-writing/`：保留的学术写作方法参考。
- `upstream-SKILL.md`、`source-manifest.json`、`LICENSE`：原始入口、上游来源与 MIT 许可。
- `ONLINE_EXPORT.json`：当前线上内容 ID、专用 runtimeId 及 28 个运行文件的 SHA-256、大小清单；本文档与该清单是仓库交接附件，不属于线上运行包。

写作方法来自 `zLanqing/codex-claude-academic-skills`。具体来源提交及文件级归属以原始 `source-manifest.json` 为准；上游原文、许可和来源记录保持原始字节；原始上游文件保持原字节。运行桥接按当前 runtime 迁移更新；最新线上版本以 ONLINE_EXPORT.json 的回读清单为准。

## 改造范围

适配中文论文/综述任务，从冻结用户需求、核验来源和论证规划，到机械检查、真实独立审查、PDF 逐页检查与 `portal-result.json` 交付。不生成假审查、虚构数据或学术认证。

## 运行依赖与边界

这不是下载后在任意电脑上即可完整运行的离线写作程序：

1. 宿主需提供实际的网页检索、工作区文件/命令、独立子 Thread 与图像阅读能力。
2. `scripts/service-endpoints.json` 现在固定为 `runtime-local-v1` 本地命令配置，没有私网 PDF 地址或 HTTP 回退。论文 Agent 必须选择已安装 `aygent-paper-runtime` 的工作环境；依赖在构建镜像时安装，不在任务中临时安装或启动服务。
3. 前台任务需要真实任务 UUID 和 `/workspace/paper-<UUID>` 目录。不能借用其他用户或历史任务的文件。
4. 不包含云平台密钥、用户账号、需求记录、稿件、任务数据库或前台部署代码。下载本目录不等于获得平台或服务访问权限。
5. 最初导出未修改线上服务；本次迁移已将论文 Agent 绑定专用 runtime，并将桥接改为本地命令，停用原独立 PDF 服务。冻结需求、真实独立审查、哈希及逐页视觉交付门禁不变；模型配置、全局默认 runtime、前台代码和已有任务未变，也未重新生成论文。

## 校验

对 `ONLINE_EXPORT.json` 中每个文件按原始字节计算 SHA-256，应与清单一致。历史27文件导出已核对。runtime迁移后新增本地命令桥接，按实际线上清单逐文件回读；固定稿回归不冒充真实学术独立审查或公开前台验收。
