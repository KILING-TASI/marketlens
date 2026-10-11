# SPDX-License-Identifier: MIT
"""Versioned declared argument structure; no automatic semantic certification."""
from .claim_evidence import _review_v1, LABELS
from .review_io import cli, instant

ARGUMENT_FIELDS={'warrant','qualifier','falsifier'}

def text(value,label):
    if not isinstance(value,str) or not value.strip() or len(value)>10000:raise ValueError(label+'须为非空文字，最多10000字符')
    return value

def argument(value):
    if not isinstance(value,dict) or not ARGUMENT_FIELDS<=set(value) or set(value)-ARGUMENT_FIELDS-{'theoryIds'}:raise ValueError('argument须声明warrant、qualifier、falsifier')
    for key,row in ((key,value[key]) for key in ARGUMENT_FIELDS):
        if not isinstance(row,dict) or set(row)!={'text','reason'}:raise ValueError(key+'须有text和reason')
        if row['text'] is None:text(row['reason'],key+'未知原因')
        else:
            text(row['text'],key)
            if row['reason'] is not None:text(row['reason'],key+'补充说明')
    if 'theoryIds' in value:
        import json
        from ._entry import resources
        ids=value['theoryIds']
        if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids) or len(ids)!=len(set(ids)):raise ValueError('theoryIds须为不重复ID列表')
        known={x['id'] for x in json.loads((resources()/'references/theory-sources.json').read_text(encoding='utf-8'))['sources']}
        if set(ids)-known:raise ValueError('未知理论来源ID；引用本身不升级证据')
    return value

def binding(value,cutoff):
    fields={'origin','proposedBy','proposedAt','status','reviewedBy','reviewedAt','reviewBasis'}
    if not isinstance(value,dict) or set(value)!=fields:raise ValueError('binding须明确提出者、提出时间、复核状态、复核者、时间及依据')
    if value['origin'] not in ('human','ai','other') or value['status'] not in ('proposed','reviewed'):raise ValueError('关联来源或复核状态无效')
    text(value['proposedBy'],'提出者');proposed=instant(value['proposedAt'])
    if value['status']=='proposed':
        if any(value[k] is not None for k in ('reviewedBy','reviewedAt','reviewBasis')):raise ValueError('待复核建议不能同时填写已复核字段')
        return 'proposal-not-reviewed'
    text(value['reviewedBy'],'复核者');text(value['reviewBasis'],'复核依据');reviewed=instant(value['reviewedAt'])
    if reviewed<proposed:raise ValueError('复核时间不能早于提出时间')
    if proposed>instant(cutoff) or reviewed>instant(cutoff):return 'binding-after-cutoff'
    return None

def review(spec):
    if not isinstance(spec,dict) or set(spec)!={'inputSchema','evidence','claims'} or spec['inputSchema']!='claim-evidence/2':raise ValueError('须为claim-evidence/2')
    claims=spec['claims']
    if not isinstance(claims,list) or not 1<=len(claims)<=100:raise ValueError('需1至100条主张')
    projected=[];metadata={}
    for c in claims:
        if not isinstance(c,dict) or set(c)!={'id','text','subjectId','referencePeriod','links','argument'}:raise ValueError('v2主张须有身份、期间、links及argument')
        argument(c['argument']);text(c['id'],'主张ID')
        if c['id'] in metadata:raise ValueError('主张ID重复')
        if not isinstance(c['links'],list) or len(c['links'])>100:raise ValueError('关联最多100项')
        old=[];pending=[];bindings={};all_links=[]
        for link in c['links']:
            if not isinstance(link,dict) or set(link)!={'evidenceId','relation','rationale','binding'}:raise ValueError('v2关联须有binding审计信息')
            if link['relation'] not in ('supports','contradicts','partial','context'):raise ValueError('声明关系无效')
            text(link['rationale'],'关联理由');text(link['evidenceId'],'资料ID')
            if link['evidenceId'] in bindings:raise ValueError('同条主张关联资料重复')
            reason=binding(link['binding'],spec['evidence']['asOf']);plain={k:link[k] for k in ('evidenceId','relation','rationale')}
            all_links.append(plain);bindings[link['evidenceId']]=link['binding']
            if reason:pending.append(dict(link,exclusion=reason))
            else:old.append(plain)
        base={k:c[k] for k in ('id','text','subjectId','referencePeriod')}
        projected.append(dict(base,links=old));metadata[c['id']]=dict(argument=c['argument'],bindings=bindings,pending=pending,allLinks=all_links)
    # Validate all proposed references too; a proposal does not bypass identity/schema checks.
    all_spec=dict(inputSchema='claim-evidence/1',evidence=spec['evidence'],claims=[dict(c,links=metadata[c['id']]['allLinks']) for c in projected])
    _review_v1(all_spec)
    result=_review_v1(dict(inputSchema='claim-evidence/1',evidence=spec['evidence'],claims=projected))
    counts={k:0 for k in LABELS};pending_count=0
    for row in result['records']:
        meta=metadata[row['id']];row['reviewProgress']='有待复核或截止后关联' if meta['pending'] else '仅记录已声明复核，人员身份未认证';row['argument']=meta['argument'];row['proposedOrDeferredLinks']=meta['pending'];pending_count+=len(meta['pending']);counts[row['status']]+=1
        for key in ('admitted','excluded'):
            for link in row[key]:link['binding']=meta['bindings'][link['evidenceId']];link['reviewIdentityVerified']=False
        row['argumentSemanticsVerified']=False
    result.update(methodVersion='claim-evidence/2',statusCounts=counts,proposedOrDeferredCount=pending_count)
    import json,hashlib
    from ._entry import resources
    catalog_bytes=(resources()/'references/theory-sources.json').read_bytes()
    catalog=json.loads(catalog_bytes.decode('utf-8'))
    used_theories={tid for c in claims for tid in c['argument'].get('theoryIds',[])}
    result['theorySources']=[r for r in catalog['sources'] if r['id'] in used_theories]
    result['theoryRegistrySha256']=hashlib.sha256(catalog_bytes).hexdigest()
    result['conclusion']=('原创教学资料。' if spec['evidence'].get('sampleType')=='teaching' else '')+f"本次核对{len(claims)}条主张，{counts['partial-only']}条只有局部支持，{counts['context-only']}条只有背景，{counts['conflicting']}条存在声明冲突；另有{pending_count}项建议或截止后关联未纳入判断。直接支持也仅限所声明对象与期间，原文仍需核查。"
    result['limitations']+=['论证依据、限定和推翻条件由输入者声明；字段完整不认证推理或结论','关联复核者和依据是声明记录，程序不认证人员身份或其实际复核行为','AI或人工提出的待复核建议单列，不纳入证据状态，不数票、不排序、不生成可信概率']
    return result

def main(argv=None):
    import sys
    old=sys.argv
    if argv is not None:sys.argv=[old[0],*argv]
    try:return cli({'review':review},'市场消息的依据、推断与证据缺口')
    finally:sys.argv=old

if __name__=='__main__':raise SystemExit(main())
