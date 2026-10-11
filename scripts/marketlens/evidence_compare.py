# SPDX-License-Identifier: MIT
"""Compare frozen reviews without recomputing historical conclusions."""
def compare(previous,current):
    for result in (previous,current):
        if not isinstance(result,dict):raise ValueError('冻结结果须为对象')
        if result.get('methodVersion') not in ('source-review/1','source-review/2'):raise ValueError('只比较市场明镜原文核对结果')
        for kind in ('sources','claims'):
            if not isinstance(result.get(kind),list) or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) for r in result[kind]):raise ValueError('冻结结果资料或主张字段无效')
            ids=[r['id'] for r in result[kind]]
            if any(not sid.strip() for sid in ids) or len(set(ids))!=len(ids):raise ValueError('冻结结果ID须非空且唯一，不能覆盖同名记录')
        source_ids={r['id'] for r in result['sources']}
        metric_rows=result.get('announcementMetrics',[])
        if not isinstance(metric_rows,list) or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) or not r['id'].strip() or not isinstance(r.get('sourceId'),str) or r['sourceId'] not in source_ids for r in metric_rows):raise ValueError('冻结指标记录或来源引用无效')
        metric_ids={r['id'] for r in metric_rows}
        if len(metric_ids)!=len(metric_rows):raise ValueError('冻结指标ID不得重复')
        bindings=result.get('metricBindings',[]);claim_ids={r['id'] for r in result['claims']}
        if not isinstance(bindings,list) or any(not isinstance(b,dict) or not isinstance(b.get('claimId'),str) or b['claimId'] not in claim_ids or not isinstance(b.get('metricId'),str) or b['metricId'] not in metric_ids for b in bindings):raise ValueError('冻结指标关联引用无效')
        for claim in result['claims']:
            if not isinstance(claim.get('text'),str):raise ValueError('冻结主张文字无效')
            for kind in ('links','checks','aspectChecks'):
                refs=claim.get(kind,[])
                if not isinstance(refs,list) or any(not isinstance(r,dict) or (r.get('sourceId') is not None and (not isinstance(r['sourceId'],str) or r['sourceId'] not in source_ids)) for r in refs):raise ValueError('冻结主张引用不存在或字段无效')
    old={r['id']:r for r in previous['sources']};new={r['id']:r for r in current['sources']}
    changes=[]
    def stable(value):
        if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('observedAt','checkedAt')}
        if isinstance(value,list):return [stable(v) for v in value]
        return value
    for sid in sorted(set(old)|set(new)):
        fields=['actualSha256','sourceRead','excerpt','excerptFound','urlCheck','timeCheck','expectedSha256','hashMatch','page','locatorVerified','sourceUrl','publishedAt','title','sourceVersion','subjectId','sourceType','registeredAttachments','extractionCoverage','attachmentCoverage']
        changed=fields if sid not in old or sid not in new else [f for f in fields if stable(old[sid].get(f))!=stable(new[sid].get(f))]
        if changed:changes.append(dict(sourceId=sid,change='added' if sid not in old else 'removed' if sid not in new else 'changed',fields=changed))
    changed_ids={r['sourceId'] for r in changes};old_claims={c['id']:c for c in previous['claims']};affected=[]
    old_metrics={r['id']:r for r in previous.get('announcementMetrics',[])};new_metrics={r['id']:r for r in current.get('announcementMetrics',[])}
    metric_changes=[mid for mid in sorted(set(old_metrics)|set(new_metrics)) if old_metrics.get(mid)!=new_metrics.get(mid)]
    all_bindings=previous.get('metricBindings',[])+current.get('metricBindings',[])
    attachments=[]
    for result in (previous,current):
        relations=result.get('sourceRelations',[])
        if not isinstance(relations,list) or any(not isinstance(r,dict) or not isinstance(r.get('from'),str) or not isinstance(r.get('to'),str) for r in relations):raise ValueError('冻结来源关系无效')
        attachments.extend(r for r in relations if r.get('type')=='attachment')
    for claim in current['claims']:
        linked={x.get('sourceId') for kind in ('links','checks','aspectChecks') for x in claim.get(kind,[]) if x.get('sourceId') is not None}
        bound={b['metricId'] for b in all_bindings if b['claimId']==claim['id']}
        for mid in bound:
            for metric in (old_metrics.get(mid),new_metrics.get(mid)):
                if metric:linked.add(metric['sourceId'])
        # Walk only explicitly registered attachment edges; finite set also handles cycles.
        while True:
            expanded=linked|{r['from'] for r in attachments if r['to'] in linked}
            if expanded==linked:break
            linked=expanded
        changed_bindings=[b for b in previous.get('metricBindings',[]) if b['claimId']==claim['id']]!=[b for b in current.get('metricBindings',[]) if b['claimId']==claim['id']]
        if linked & changed_ids or bound & set(metric_changes) or changed_bindings or old_claims.get(claim['id'])!=claim:affected.append(dict(id=claim['id'],text=claim['text'],sources=sorted(linked & changed_ids),metrics=sorted(bound & set(metric_changes)),reason='资料、指标关联或核对记录变化，需重新复核；不自动改历史结论'))
    removed=[dict(id=c['id'],text=c['text'],reason='本轮已移除该主张；旧记录保留') for c in previous['claims'] if c['id'] not in {x['id'] for x in current['claims']}]
    context_fields=['announcementMetrics','sourceRelations','searchLog','researchPlan','metricBindings']
    context_changes=[f for f in context_fields if previous.get(f)!=current.get(f)]
    rows=[(c['sourceId'],c['change']+'；变化字段：'+','.join(c['fields'])) for c in changes]+[(c['text'],c['reason']) for c in affected+removed]+[(f,'研究记录变化，需复查对应口径与结论范围') for f in context_changes]
    return dict(methodVersion='source-review-diff/1',conclusion='对比冻结结果：'+str(len(changes))+'项资料变化，'+str(len(affected))+'条当前主张需复查，'+str(len(context_changes))+'项研究记录变化；不重算或覆盖历史。',sourceChanges=changes,metricChanges=metric_changes,affectedClaims=affected,removedClaims=removed,contextChanges=context_changes,humanRows=rows,limitations=['按ID与字段比较，身份映射由输入者保留；ID变化不证明不同对象。','只沿明确登记的指标关联提示主张，不推断缺失关联。','只指出变更影响范围，不自动判定哪个版本真实或有效。'])
