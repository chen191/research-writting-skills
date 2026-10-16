"""Non-academic engineering fixture. No review PASS and no ready delivery."""
TITLE='论文排版执行环境迁移的中文长标题与分页边界固定样例'
SOURCE={'id':'S1','title':'Aygent runtime source (engineering fixture reference)',
        'url':'https://github.com/aygenta-ai/aygenta/blob/a07547f3b12849d21f32acadb543c378124a93a8/server/runtime.ts',
        'evidence_level':'user_provided','locator':'Local fixed engineering sample; not research evidence',
        'evidence':'Only checks formatting, source identifiers and escaped literal text.',
        'retrieval':'No network retrieval performed by this deterministic fixture.'}

def payload(profile):
    intro='本样例仅用于检查执行环境迁移后的字体、目录、页边距与分页表现，不用于研究成果交付，也不代表学校格式认证。检查采用固定文本与固定引用，不由语言模型重新生成正文。本文将页面元素拆分为封面、双语摘要、目录、章节、表格与参考文献，从实际输出观察中文是否完整、标题是否越界以及引用是否正确链接。[S1]'
    method='执行环境在编译前保存当前输入，随后使用受限的命令行参数完成排版。中文正文应保持连续阅读，段落中的百分号、下划线和反斜杠均按普通字符显示，不允许成为可执行命令。长表格应保留原始列方向，跨页时重复表头，末行不应超出纸张边界。这里不引入真实作者、导师、学号或学校身份，避免将版式验证误解为正式论文认证。[S1]'
    result='观察对象包含目录页码、表格边界、章节层次与参考文献的标记。页面中可以出现合理留白，但不能把缺失内容当成留白解释。所有内容均为工程样例，不能当作真实实验数据或研究结论。结果的判断依据是实际编译日志、文本提取、页面尺寸和逐页图像，而非单独依赖文件存在。本文不声明已经通过独立学术审查，也不构造审查者身份。'
    conclusion='本样例说明迁移验证只需重复使用确定性的工程文本，不必为每次编译消耗模型生成长文。编译器可用并不等于稿件具有学术价值，视觉正常也不能替代来源核验。正式用户任务仍需真实独立审查与完整视觉检查。后续维护应固定依赖来源，记录模板版本，并在变更时验证现有下载契约，防止将运行环境更新与内容质量混为一谈。'
    table='| 序号 | 检查对象 | 固定说明 |\n|---|---|---|\n'+'\n'.join(f'| {i} | 分页元素{i} | 固定记录，观察表头与列宽是否保持一致，不代表实验结果。 |' for i in range(1,37))
    md=f'# {TITLE}\n\n## 摘要\n\n{intro}\n\n关键词：执行环境；中文排版；固定样例\n\n## Abstract\n\nThis is a fixed engineering fixture for typography and pagination only. It is not a research paper or an academic approval.\n\nKeywords: runtime; typography; fixture\n\n## 引言\n\n{intro}\n\n## 方法与表格\n\n{method}\n\n### 表1 跨页固定记录\n\n{table}\n\n## 边界与限制\n\n{result}\n\nLiteral input: `\\input{{/etc/passwd}}`, 50%, a_b, A&B.\n\n## 结语\n\n{conclusion}\n\n## 参考文献\n\n[S1] Aygent runtime source. https://github.com/aygenta-ai/aygenta . Fixed engineering reference, not academic evidence.\n'
    return {'title':TITLE,'template':profile,'markdown':md,'sources':[SOURCE],
            'requirements':{'min_chinese':400,'min_sources':1},
            'audit':{'scope':'Engineering layout preflight only. No independent review was performed; not a deliverable.'}}
