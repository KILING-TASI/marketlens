# SPDX-License-Identifier: MIT
"""ACH-inspired qualitative comparison; not original ACH ranking or probability."""
from .argument_review import review as arguments
from .review_io import cli

def review(spec):
    if not isinstance(spec,dict) or set(spec)!={'inputSchema','evidence','hypotheses'} or spec['inputSchema']!='competing-hypotheses/1':raise ValueError('须为competing-hypotheses/1')
    hypotheses=spec['hypotheses']
    if not isinstance(hypotheses,list) or not 2<=len(hypotheses)<=5:raise ValueError('声明2至5个竞争解释；不假定解释集穷尽或互斥')
    result=arguments(dict(inputSchema='claim-evidence/2',evidence=spec['evidence'],claims=hypotheses));matrix=[]
    for e in result['evidenceReview']['records']:
        cells=[]
        for h in result['records']:
            included=next((x for x in h['admitted'] if x['evidenceId']==e['id']),None)
            excluded=next((x for x in h['excluded']+h['proposedOrDeferredLinks'] if x['evidenceId']==e['id']),None)
            cells.append(dict(hypothesisId=h['id'],relation=included['relation'] if included else None,reason=included['rationale'] if included else excluded['exclusion'] if excluded else '未声明这项比较；保持未知'))
        roles=[c['relation'] for c in cells]
        pattern='incomplete' if None in roles else 'declared-difference' if len(set(roles))>1 else 'same-declared-relation'
        matrix.append(dict(evidenceId=e['id'],cells=cells,comparisonStatus=pattern,diagnosticityVerified=False))
    result.update(methodVersion='competing-hypotheses/1',hypothesisMatrix=matrix)
    result['conclusion']=f"已并列{len(hypotheses)}种解释。声明关系不同的材料提示应优先复查区分依据；缺失单元格保持未知。没有自动排除、确认或排序任何解释，解释集也未证明穷尽。"
    titles={h['id']:h['text'] for h in hypotheses}
    material={e['id']:e for e in result['evidenceReview']['records']}
    names={'supports':'声明支持','contradicts':'声明反对','partial':'仅局部支持','context':'仅作背景',None:'未知，未完成比较'}
    result['humanRows']=[[str(material[m['evidenceId']].get('locator') or '材料')+'：'+str(material[m['evidenceId']].get('excerpt') or '未取得摘录')[:80],'；'.join(titles[c['hypothesisId']]+'：'+names[c['relation']] for c in m['cells'])] for m in matrix]
    result['limitations']+=['仅借鉴Heuer第八章的竞争解释、诊断性和反证检查；原版ACH也讨论相对可能性，本工具不实现其排序步骤','声明contradicts不自动证伪；推翻条件与关键证据仍须核实，同一文件的重复材料不增加独立支持']
    return result

def main(argv=None):
    import sys
    old=sys.argv
    if argv is not None:sys.argv=[old[0],*argv]
    try:return cli({'review':review},'竞争解释与证据对照')
    finally:sys.argv=old

if __name__=='__main__':raise SystemExit(main())
