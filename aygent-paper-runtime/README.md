# Aygent 论文 Runtime

将正式论文 PDF 能力打包为 Aygent 工作环境内的按需命令，不再部署独立 PDF HTTP 服务。只供 `research-writing-aygent` 的机械检查、LaTeX 编译和逐页预览调用；不调用模型、不写论文、不生成审查或视觉 PASS。

## 结构与依赖

- `Dockerfile`：从当前平台固定 digest 的 Debian 13 runtime 继承，保留 `/etc/container-entrypoint.sh` 和已有桌面/浏览器能力；离线迁入原编译镜像的同版 XeLaTeX、latexmk、中文/数学排版包及 Python 模块。不新增监听端口、服务监督项或数据卷。
- `collect_toolchain.py`：仅在构建阶段按白名单复制 TeX、字体、Perl 模块和编译器依赖；Python 包放在私有目录，编译共享库只对该命令及子进程生效。不复制原 HTTP 应用、Python 解释器、模型 SDK 或 `/data`。依赖版本、二进制哈希及第三方版权保存在镜像的 `TOOLCHAIN.json` 和 `third-party-notices/`。
- `engine/cli.py`：`doctor` / `check` / `render` / `preview`，JSON stdin/stdout。生成文件只进入 `/workspace/paper-UUID/.paper-render/` 和本任务预览目录；不处理远程 URL，不执行用户 LaTeX。
- `engine/latex_render.py`、`mechanics.py`、`template_profiles.py`、`pdf_preview.py`：从当前正式编译服务按原字节迁入，见 `ORIGIN.json`；没有把历史测试学校的 profile 切到正式前台。
- `engine/validation.py`：保留原服务完整输入门禁，不携带 HTTP server、旧 evidence-gate 路由、模型依赖或服务数据。
- `tests/`：固定非科研测试文稿及迁移回归，不伪造实际独立审查、学校认证或 ready 交付。

正式 Skill 只支持既有 `generic-paper-v1`、`sjtu-paper-v1`。这里不增加学校模板、不改变前台界面、账号、模型连接或默认模型。上游 SJTUTeX 的版权和 LPPL 来源文件保留。

## 契约

编译前仍须 freeze → check → 实际 fresh/sync 独立审查 → accept-review；render 标记禁止未知结果重放。PDF 编译后仍须全部页实际图像检查，publish 的 request/source/manuscript 哈希和 review/visual 门禁不变。产物最终仍由原 Thread 文件 API 和前台结果索引下载，不需要访问旧22022服务。

迁移使用固定稿执行确定性测试，不将测试夹具的 mock 审查当成真实学术审查，也不重新生成长论文消耗模型 token。`python -m unittest discover -s aygent-paper-runtime/tests -p test_runtime.py` 检查迁移门禁；`tests/preflight.py` 在隔离容器中直接测试排版核心，并明确验证缺少独立审查时正式 render 被拒绝，绝不生成 accepted-review 或 ready 索引。

## 构建与回退

源编译器阶段依赖本机已验证的原 PDF 镜像 ID。正式登记通过 Aygent Runtime API 构建并保存源码，论文 Agent 绑定专用 runtimeId，不修改全局 Base Runtime。部署前须保存原 Agent、Skill 清单和镜像；校验完成且没有旧链路在途任务后，才停用原独立服务，保留原镜像和数据卷以便回退。

Git 源码同步与线上部署分离，推送不会自动更新线上 runtime 或 Agent 绑定。删除本目录会失去可复现构建源与长期回归，已经登记的线上 runtime 镜像不会自动被删除。
