# 主张、推理与复核记录

使用claim-evidence/2；旧claim-evidence/1输入及计算结果保持兼容。新输入顶层仍为inputSchema/evidence/claims，evidence沿用evidence-status/1。

每条主张保留id/text/subjectId/referencePeriod/links，新增argument：warrant（资料如何支持主张）、qualifier（对象/期间/条件限定）、falsifier（何种新证据会要求推翻或改写）。每项为{text, reason}：未知时text=null且reason必须非空；已声明text时reason可以为空。可选theoryIds只引用目录中的ID，不据此提升结论。

每条link保留evidenceId/relation/rationale，新增binding：origin=human/ai/other、proposedBy、proposedAt、status=proposed/reviewed、reviewedBy、reviewedAt、reviewBasis。proposed时三个复核字段须为null；reviewed时须完整声明人员、时间与依据，且复核不能早于提出或晚于本次截止时间。未复核或截止后关联单列，不纳入六类主张状态。

所有人员和复核记录均为输入声明。declared不等于人工确认，程序不认证复核者身份、实际复核行为、原文含义或担保效力。原文是否读过、来源是否独立、资料当时是否已公开，是不同问题。

报告先回答证据在什么范围支持判断，再展示六类状态、论证限定、建议关联及缺口。缺资料不能输出“消息为假”；明确的反对材料可以解释它反对哪个具体主张，但不升级为整体真假认证。简单问题不强制使用长矩阵。
