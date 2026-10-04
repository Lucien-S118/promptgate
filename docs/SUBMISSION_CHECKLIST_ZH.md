# PromptGate 提交与演示清单

依据：用户在 2026 年 10 月 2 日提供的老师公告截图，以及 9 月 23 日反馈。截止：2026 年 10 月 4 日 23:59，新加坡时间。此清单是操作辅助，不替代提交页面的最终要求。

## 已准备的材料

- `TRADEOFF_REPORT.md`：约 1,100 词英文报告，包含结论、取舍、指标批判、困难与局限。
- `output/docx/PE6201_PromptGate_Tradeoff_Report_SIwen_Liu.docx`：可编辑报告。
- `output/pdf/PE6201_PromptGate_Tradeoff_Report_SIwen_Liu.pdf`：排版后报告，提交时优先选择页面接受的格式。
- `docs/PRODUCT.md`：用户画像、输入输出、架构图、目标和实测指标。
- `data_sources/README.md`、`evals/README.md`：数据与评估说明；对应数据快照、模型和逐条预测在仓库中。
- `docs/MODULES.md`：文件与模块说明。
- `DEMO_SCRIPT.md`：约 230 词的短版出镜加屏幕演示稿，附逐段中文对照；为读稿与操作预留时间，视频实际时长仍以成片为准。
- 原 Problem Statement 仍使用 8 月提交版本，不把后来的结果倒填成原提案。

## 你需要亲自确认或完成

1. 阅读报告并确认它准确代表你的项目选择；能解释下方五个要点，不能只照念。
2. 确认 GitHub 账号、仓库名称和可见性。私有仓库必须让老师／助教获得实际访问权限；仅贴私有链接不够。登录与双重认证由本人完成，不把密码或令牌发到聊天。
3. 确认数据提交例外：deepset 是否可按原反馈保持 eval-only，只交来源、固定版本、校验值及无原文预测。下方提供可发送草稿，但尚未发送。
4. 录制真人出镜加屏幕，约 5 分钟。先录 15 秒测试音量与摄像头，再完整录制。不要显示密钥、邮箱或个人文件。
5. 回放确认声音、脸部、运行结果与字迹清楚，实际时长在 2–8 分钟范围。
6. 用户提供的提交入口截图显示：可填写正文和上传文件，上传区域标注 500 MB，尝试次数不限，已有一次提交记录，没有额外作业说明。最终仍需检查实际附件限制和历史记录；上传报告、代码仓库链接、视频及原 Problem Statement，代码 ZIP 可作为私有仓库访问的备用。不要把历史记录当作最终材料已齐全，也不假定有固定文件名要求。
7. 最终点击提交前检查姓名 SIwen Liu、课程、全部附件和链接；提交后保存回执。文件准备好不等于已经提交。

## 演示前必须能解释的五点

- 为什么用分类器：任务是有标签、边界明确的分类；LLM 仅解释，不拥有放行权。
- 4.0% 与 36.8% 为什么不同：前者是开发集上的二分类误报率，后者是外部数据上的实际混合策略误报率；样本和策略都要说清楚。
- 为什么 Review 不算正确拦截：它只是暂扣交人工，未测过人工是否纠正；正常输入也会被暂扣。
- 为什么还不能生产部署：外部误报与审核工作量太高，且没有真实 RAG 集成、认证和持久审批流程。
- 哪些是实测：离线模型预测、100 次真实基线调用；哪些只是测试：模拟供应商回复；哪些是未来计划：企业标签、漂移监控和人工审核效果研究。

## 数据边界确认草稿

### 英文原文

Dear Ajay,

Thank you for the clarification. For PromptGate, I have included the S-Labs data used, the split audit, evaluation code and text-free prediction records. In line with the eval-only treatment discussed in your feedback, I have not redistributed the deepset prompt text because its licence metadata conflicts. Instead, the repository provides the pinned source links, checksums and a local acquisition script. Is this acceptable for the data check-in requirement, or would you prefer another submission arrangement?

Best regards,
SIwen Liu

### 中文对照

Ajay 老师您好：

感谢您对提交物的补充说明。PromptGate 已包含使用的 S-Labs 数据、划分审计、评估代码和不含提示词原文的预测记录。根据您反馈中讨论的仅用于评估的处理方式，我没有重新分发许可元数据存在冲突的 deepset 提示词原文，而是在仓库中提供固定版本来源链接、校验值和本地获取脚本。请问这样是否满足数据提交要求，还是您希望采用其他提交安排？

此致，
SIwen Liu

## 学术诚信与最终确认

材料由你审阅后以你的项目身份提交；不得将协助生成的文字当作自己已经掌握的证据，也不得声称未使用 AI。如课程或提交页面要求 AI 使用声明，应如实说明所用工具及协助范围。此清单不替你确认不存在额外声明要求。
