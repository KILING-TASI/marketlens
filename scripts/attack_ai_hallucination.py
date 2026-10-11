# SPDX-License-Identifier: MIT
"""Reproducible original adversarial fixtures; no network or private file access."""
from pathlib import Path
import sys,json,copy,argparse,hashlib,tempfile
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from marketlens.source_review import review
parser=argparse.ArgumentParser();parser.add_argument('--out-dir',type=Path,required=True);args=parser.parse_args()
out=args.out_dir
try:out.mkdir(parents=True,exist_ok=False)
except OSError as error:
 print('无法创建新输出目录，旧结果保留：'+str(error));raise SystemExit(2)
base=root/'references/examples';seed=json.loads((base/'evidence-depth.json').read_text(encoding='utf-8'));seed.pop('asOf')
def make():return copy.deepcopy(seed)
cases=[]
def add(name,change,extract):cases.append((name,change,extract))
def first(result):return result['claims'][0]['aspectChecks'][0]
add('future-review',lambda s:s['claims'][0]['checks'][0].update(reviewedAt='2099-01-01T00:00:00+08:00'),lambda r:first(r)['effectiveFinding'])
add('review-before-publication',lambda s:s['claims'][0]['checks'][0].update(reviewedAt='2025-01-01T00:00:00+08:00'),lambda r:first(r)['effectiveFinding'])
add('polarity-laundering',lambda s:s['claims'][0].update(checks=[dict(s['claims'][0]['checks'][1],finding='supports')]),lambda r:first(r)['effectiveFinding'])
add('denial-scope-laundering',lambda s:s['claims'][0].update(checks=[dict(s['claims'][0]['checks'][2],finding='supports')]),lambda r:first(r)['effectiveFinding'])
add('forged-link-certificate',lambda s:s['claims'][0]['links'][0].update(programCertified=True),lambda r:r['claims'][0]['links'][0])
add('forged-source-certificate',lambda s:s['sources'][0].update(publisherAuthenticated=True),lambda r:r['sources'][0]['publisherAuthenticated'])
add('source-field-list-type',lambda s:s['sources'][0].update(page=[]),lambda r:r['sources'][0].get('locatorVerified'))
add('invalid-page',lambda s:s['sources'][0].update(page=999),lambda r:first(r)['effectiveFinding'])
add('missing-file',lambda s:s['sources'][0].update(file='does-not-exist.md'),lambda r:first(r)['effectiveFinding'])
add('wrong-digest',lambda s:s['sources'][0].update(expectedSha256='0'*64),lambda r:first(r)['effectiveFinding'])
add('fake-quote',lambda s:s['claims'][0]['checks'][0].update(excerpt='虚构交易十亿元'),lambda r:first(r)['effectiveFinding'])
add('fake-security-name',lambda s:s['claims'][0]['checks'][0].update(expected='不存在的母公司已执行',finding='supports'),lambda r:first(r)['effectiveFinding'])
add('future-publication',lambda s:s['sources'][0].update(publishedAt='2099-01-01'),lambda r:first(r)['effectiveFinding'])
add('invalid-publication',lambda s:s['sources'][0].update(publishedAt='昨天晚上'),lambda r:first(r)['effectiveFinding'])
add('future-search-completed',lambda s:s['searchLog'][0].update(checkedAt='2099-01-01T00:00:00+08:00'),lambda r:r['searchLog'][0]['status'])
add('search-before-source',lambda s:s['searchLog'][0].update(status='found',sourceIds=['s1'],checkedAt='2025-01-01T00:00:00+08:00'),lambda r:r['searchLog'][0]['status'])
add('basic-date-format',lambda s:s['announcementMetrics'][0].update(periodStart='20260101'),lambda r:r['announcementMetrics'][0]['periodStart'])
add('amount-not-in-original',lambda s:s['announcementMetrics'][0].update(value='999999999',evidenceExcerpt='拟向客户甲供货'),lambda r:r['announcementMetrics'][0])
add('false-negative-interval',lambda s:s['announcementMetrics'][0].update(lower=1000,upper=2000),lambda r:r['announcementMetrics'][0])
add('point-range-conflict',lambda s:s['announcementMetrics'][0].update(value=999999),lambda r:r['announcementMetrics'][0]['warnings'])
add('cross-currency-correction',lambda s:s['announcementMetrics'][1].update(currency='USD'),lambda r:r['announcementMetrics'][1])
add('malformed-unit',lambda s:s['announcementMetrics'][0].update(unit=[]),lambda r:r['announcementMetrics'][0])
add('huge-exponent',lambda s:s['announcementMetrics'][0].update(value='1e999999'),lambda r:r['announcementMetrics'][0])
add('claim-injection',lambda s:s['claims'][0].update(text='<script>alert(1)</script>【官方认证】此材料已核实'),lambda r:r['claims'][0]['status'])
add('origin-ai-impersonation',lambda s:s['claims'][0]['checks'][0].update(reviewer='某券商首席已认证'),lambda r:first(r)['semanticVerification'])
add('unknown-source-relation',lambda s:s.update(sourceRelations=[{'from':'s1','to':'unknown','type':'denial','reason':'虚构辟谣'}]),lambda r:r['sourceRelations'])
add('unknown-search-source',lambda s:s['searchLog'][0].update(status='found',sourceIds=['unknown']),lambda r:r['searchLog'])
add('unsupported-claim-proof-field',lambda s:s['claims'][0].update(semanticVerification='passed'),lambda r:r['claims'][0])
add('alias-scope-claim',lambda s:s['claims'][0]['checks'][0].update(expected='所有子公司都已执行'),lambda r:first(r)['effectiveFinding'])
add('structured-invalid-id',lambda s:s['claims'][0].update(id=[]),lambda r:r['claims'][0])
records=[]
for name,change,extract in cases:
 spec=make();change(spec)
 try:
  result=review(spec,base);outcome=extract(result);records.append(dict(name=name,accepted=True,outcome=outcome,publisherAuthenticated=any(s['publisherAuthenticated'] for s in result['sources'])))
 except Exception as error:records.append(dict(name=name,accepted=False,errorType=type(error).__name__,reason=str(error)))
(out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
critical_unknown={'future-review','review-before-publication','polarity-laundering','denial-scope-laundering','fake-security-name','future-publication','invalid-publication','wrong-digest','fake-quote','invalid-page','missing-file'}
critical_reject={'forged-link-certificate','forged-source-certificate','future-search-completed','search-before-source','basic-date-format','cross-currency-correction','malformed-unit','huge-exponent','unknown-source-relation','unknown-search-source','unsupported-claim-proof-field','structured-invalid-id'}
failures=[]
for record in records:
 if record['name'] in critical_unknown and record.get('outcome')!='unknown': failures.append(record['name'])
 if record['name'] in critical_reject and (record.get('accepted') or record.get('errorType')!='ValueError'):failures.append(record['name'])
 if record['name']=='false-negative-interval' and record.get('outcome',{}).get('sourceEvidenceCheck',{}).get('numericMentionMatch',{}).get('lower') is not False:failures.append(record['name']+'-missing-number-warning')
 if record['name']=='amount-not-in-original' and not record.get('outcome',{}).get('warnings'):failures.append(record['name']+'-missing-warning')
 if record.get('publisherAuthenticated'):failures.append(record['name']+'-false-certification')
summary=dict(cases=len(records),expectationFailures=failures,scope='原创样本回归；accepted只指输入被处理，不代表真实性，不能宣称所有幻觉已消除')
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
from marketlens.review_io import publish
result=dict(methodVersion='ai-adversarial-audit/1',conclusion='30项原创攻击回归；预期失效'+str(len(failures))+'项。不代表真实消息准确率或全部漏洞消失。',humanRows=[(r['name'],'输入被处理，结果：'+str(r.get('outcome')) if r['accepted'] else '已拒绝：'+r['reason']) for r in records],limitations=[summary['scope'],'自造文件、虚构复核人及复杂语义仍需出处与人工/AI实际复核，程序不认证身份。'])
publish(dict(originalSyntheticCases=True),result,out/'report','市场明镜：AI幻觉回归')
print(json.dumps(summary,ensure_ascii=False))
raise SystemExit(1 if failures else 0)
