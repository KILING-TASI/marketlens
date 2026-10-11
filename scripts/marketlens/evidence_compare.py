# SPDX-License-Identifier: MIT
"""Compare frozen reviews without recomputing historical conclusions."""
def compare(previous,current):
    for result in (previous,current):
        if not isinstance(result,dict):raise ValueError('冻结结果须为对象')
        if result.get('methodVersion') not in ('source-review/1','source-review/2'):raise ValueError('只比较市场明镜原文核对结果')
        for kind in ('sources','claims'):
            if not isinstance(result.get(kind),list) or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) for r in result[kind]):raise ValueError('冻结结果资料或主张字段无效')
    old={r['id']:r for r in previous['sources']};new={r['id']:r for r in current['sources']}
    changes=[]
    def stable(value):
        if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('observedAt','checkedAt')}
        if isinstance(value,list):return [stable(v) for v in value]
        return value
    for sid in sorted(set(old)|set(new)):
        fields=['actualSha256','sourceRead','excerpt','excerptFound','urlCheck','timeCheck']
        changed=fields if sid not in old or sid not in new else [f for f in fields if stable(old[sid].get(f))!=stable(new[sid].get(f))]
        if changed:changes.append(dict(sourceId=sid,change='added' if sid not in old else 'removed' if sid not in new else 'changed',fields=changed))
    changed_ids={r['sourceId'] for r in changes};old_claims={c['id']:c for c in previous['claims']};affected=[]
    for claim in current['claims']:
        linked={x['sourceId'] for x in claim.get('links',[])}|{x['sourceId'] for x in claim.get('checks',[]) if x['sourceId'] is not None}
        if linked & changed_ids or old_claims.get(claim['id'])!=claim:affected.append(dict(id=claim['id'],text=claim['text'],sources=sorted(linked & changed_ids),reason='资料或核对记录变化，需重新复核；不自动改历史结论'))
    removed=[dict(id=c['id'],text=c['text'],reason='本轮已移除该主张；旧记录保留') for c in previous['claims'] if c['id'] not in {x['id'] for x in current['claims']}]
    rows=[(c['sourceId'],c['change']+'；变化字段：'+','.join(c['fields'])) for c in changes]+[(c['text'],c['reason']) for c in affected+removed]
    return dict(methodVersion='source-review-diff/1',conclusion='对比冻结结果：'+str(len(changes))+'项资料变化，'+str(len(affected))+'条当前主张需复查；不重算或覆盖历史。',sourceChanges=changes,affectedClaims=affected,removedClaims=removed,humanRows=rows,limitations=['按ID与字段比较，身份映射由输入者保留；ID变化不证明不同对象。','只指出变更影响范围，不自动判定哪个版本真实或有效。'])
