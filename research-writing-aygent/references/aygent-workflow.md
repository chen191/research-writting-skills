# 当前科研前台工作流

本文件是宿主适配，不是上游写作指南。设 `S` 为本 Skill 真实挂载目录，`W=/workspace/paper-<用户消息中的任务UUID>`。所有正文、来源和审查保存在 W；不得创建额外后台根任务/账号。

## 文件与命令

`request-input.json` 格式：

```json
{"task_id":"消息提供的UUID","title":"用户题目","word_target":2000,"min_sources":8,"template":"generic-paper-v1","requirements":"用户补充要求原文"}
```

上述 2000/8 只是结构示例，必须替换为真实需求；不预设题目、篇幅或任意缩小范围。`requirements` 为字符串。消息没有任务 UUID 的非前台写作，不使用 publish，不伪造 UUID。

```sh
python3 "$S/scripts/paper.py" freeze --workdir "$W" --input "$W/request-input.json"
# 亲自检索与撰写 outline.md、sources.json、paper.md
python3 "$S/scripts/paper.py" check --workdir "$W"
python3 "$S/scripts/paper.py" review-input --workdir "$W"
# 真实独立 create_thread，子 Thread 写 review.json 并最终原样返回它
python3 "$S/scripts/paper.py" accept-review --workdir "$W" --input "$W/native-review-return.json"
python3 "$S/scripts/paper.py" render --workdir "$W"
python3 "$S/scripts/paper.py" preview --workdir "$W"
# 真实逐页 view_image，再自行判断并保存 visual-review.json
python3 "$S/scripts/paper.py" publish --workdir "$W"
```

freeze 是本包的需求 prepare，生成不可替换的 request.json。当前前台消息中的 `paper_result.py` 指本包的 `scripts/paper_result.py --workdir "$W"`；它仅调用上述 publish，不需要另一个Skill。Sources 是 JSON 数组，每条示例：

```json
{"id":"S1","title":"真实题名","url":"https://原始论文或官方页面","authors":["真实作者"],"year":2024,"doi":"可核验时填写","evidence_level":"abstract","locator":"原始页 Abstract 段落","evidence":"实际读取的摘要要点，不扩张成全文结果","retrieval":"本任务真实原生搜索/打开的调用或页面记录"}
```

没有 DOI 的官方来源可省略，不猜填。网页只显示题录且没有足以支持论断的摘要/全文时，留在候选笔记，不放入正文可引用的 sources。用户提供资料注明实际范围，不能冒充网络读取。脚本校验台账结构，不自行检索、不决定语义真实性；独立审查者核对所引用的内容与原始来源。

## 当前独立子 Thread

用宿主实际 `create_thread`，`agentId=null`，`context=fresh`，`mode=sync`，`resources={workspace:shared,root:shared,sandbox:shared}`，`model=null` / `reasoning=null` 继承本轮，不改全站模型。description 包含角色、W、review-input.json 路径、哈希、输出路径与“自己独立阅读判断，不嵌套分派”。审查者不进入作者 freeze/render/publish 流程，也不自审自己的稿件。

`review-input.json` 已提供绑定哈希。审查者自己写 `review.json`：

```json
{"schema_version":1,"task_id":"真实任务UUID","input_hashes":{"request":"完整SHA256","manuscript":"完整SHA256","sources":"完整SHA256"},"verdict":"PASS或REVISE或BLOCKED","scope":"实际读取的范围与限制","blocking_issues":[],"notes":"对来源支持、论证和写作结构的具体判断"}
```

作者只从实际 completed 且 error 为空的工具返回映射：

```json
{"thread_id":"实际threadId","run_id":"实际runId","status":"completed","error":null,"answer":"子Thread最终原样返回的review.json文本"}
```

写到 native-review-return.json 后 accept-review；不能从磁盘内容自行伪造“工具返回”。本机离线只能校验结构与哈希，真实性须由宿主实际 History 中的调用、子 Thread 与 Run 回读确认。相同独立审查覆盖整篇。

## 视觉检查与结果

render 保存 paper.pdf、render-receipt.json 和 pdf-contact-sheet.png。preview 下载 `preview/1.png` 等所有页面，并保存 previews.json；用实际图片阅读工具逐页观察，不把下载成功当视觉 PASS。visual-review.json 示例：

```json
{"verdict":"PASS","pdf_sha256":"当前PDF的SHA256","pages_inspected":[1,2,3],"blocking_issues":[],"notes":"实际逐页观察结论，存在问题时具体定位"}
```

页数必须与真实 receipt 完全相同。修改正文、来源或需求后原机械/独立/编译/视觉证据全部失效，必须重做相应阶段。未知编译结果保留 render-request.json，停止并交管理员核实，不自动重发 POST。现有服务只支持既有模板和证据表格，不能编造新模板名、学校身份或偷偷改服务。

publish 使用当前前台既有 schema_version=1/status=ready/task_id/pdf.path/sha256/size/checks 四项契约，不改前台代码或认证。模型审查不是学术认证；用户仍需人工核对。
