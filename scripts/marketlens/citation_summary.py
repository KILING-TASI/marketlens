# SPDX-License-Identifier: MIT
from .narrative import analyze
from .review_io import cli
def summarize(spec):
    r=analyze(spec);evidence={e['id']:e for e in r['available_evidence']};rows=[]
    for claim in r['claims']:
        citations=[{'id':key,'source':evidence[key]['source'],'scope':evidence[key]['scope'],'period':[evidence[key]['period_start'],evidence[key]['period_end']],'stage':evidence[key]['stage'],'availableAt':evidence[key]['available_at'],'verifiedAt':evidence[key]['verified_at']} for key in claim['support_ids']]
        rows.append({'claimId':claim['claim_id'],'status':claim['status'],'citations':citations,'conflicts':claim['conflicts'],'scopeNote':claim['scope_note']})
    return {'conclusion':'每条主张附支持证据、行为阶段、期间与时点；证据不足或冲突一并显示，引用摘要不自动证明整句消息为真。','asOf':r['as_of'],'simulation':r['simulation'],'rows':rows,'excluded':r['excluded_evidence'],'humanRows':[[x['claimId'],x['status']] for x in rows],'limitations':r['limitations']+['引用只整理已填证据，未复制长原文；转载权利另核']}
if __name__=='__main__':raise SystemExit(cli({'summary':summarize},'市场叙事可引用核查摘要'))
