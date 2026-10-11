# 竞争解释与证据对照

借鉴Heuer《Psychology of Intelligence Analysis》第八章的竞争解释、诊断性和反证检查。原版ACH包含相对可能性判断；本工具只实现定性对照，未实现原版排序或概率步骤。

新入口：marketlens hypotheses review --input 底稿.json --out-dir 新目录。

输入competing-hypotheses/1，含evidence及2至5条hypotheses；每个解释使用claim-evidence/2的主张结构。对同一材料分别声明supports/contradicts/partial/context，未取得或未评价的单元格为null并说明原因。只有材料本身可纳入且关联已声明复核的单元格进入比较；未复核建议不参与判断。

相同声明关系不能自动证明没有区分能力，不同声明关系也不能证明真正有区分能力。comparisonStatus只报告声明模式，diagnosticityVerified保持false；contradicts不是自动证伪，解释集不假定穷尽或互斥。没有获胜解释、总分、排序或可信概率。后续应核对原文、关键假设和哪些新资料会改变判断。

例子：ETF放量可能涉及不同交易活动，但成交量不能识别具体买方；应比较公开实施披露、持仓存量及申赎记录能支持的具体范围，不能由心理学、社会学或信号理论补出匿名主体。
