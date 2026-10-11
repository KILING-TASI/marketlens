# SPDX-License-Identifier: MIT
"""Read explicitly selected artifacts; never certify publisher or truth."""
import argparse
import hashlib
import json
import re
import io
from html.parser import HTMLParser
from pathlib import Path
from .review_io import publish, read
from .evidence_details import enrich_source, links_and_search, aspects, scan, ASPECTS

LIMIT = 16 * 1024 * 1024

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('p', 'br', 'div', 'li', 'tr'): self.parts.append('\n')
        if tag in ('td','th'):self.parts.append(' | ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)

def artifact(path):
    if path.is_symlink() or not path.is_file(): raise ValueError('原文件不存在或是链接')
    if path.stat().st_size > LIMIT: raise ValueError('原文件超过16MiB限制')
    raw = path.read_bytes()
    if len(raw)>LIMIT: raise ValueError('原文件超过16MiB限制')
    if path.suffix.lower() == '.pdf':
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError: raise ValueError('PDF文本提取需要可选组件 pypdf；也可提供原文文本，不会自动安装')
        try: reader = PdfReader(io.BytesIO(raw))
        except PdfReadError as error: raise ValueError('PDF读取失败：'+str(error))
        if reader.is_encrypted: raise ValueError('加密PDF暂不支持；请提供有权读取的文本')
        if len(reader.pages)>500: raise ValueError('PDF超过500页限制，请明确提供需要核对的分册')
        pages=[]; extracted=0
        for page in reader.pages:
            content=page.extract_text() or '';extracted+=len(content)
            if extracted>LIMIT:raise ValueError('PDF提取文本超过16MiB字符限制，请按分册核对')
            pages.append(content)
    else:
        content = raw.decode('utf-8-sig')
        if path.suffix.lower() in ('.html', '.htm'):
            parser = VisibleText(); parser.feed(content); content = ''.join(parser.parts)
        elif path.suffix.lower() not in ('.txt', '.md', '.csv'):
            raise ValueError('支持UTF-8文本、HTML及可选PDF；不执行文件内容')
        pages = [content]
    return hashlib.sha256(raw).hexdigest(), pages

def alerts(text):
    return [dict(w,matched=[w['matched']]) for w in scan(text)]

def review(spec, base, verify_urls=False):
    if not isinstance(spec, dict) or spec.get('inputSchema') not in ('source-review/1','source-review/2'): raise ValueError('须为source-review/1或source-review/2')
    if set(spec)-{'inputSchema','sources','claims','announcementMetrics','sourceRelations','searchLog','researchPlan','asOf','metricBindings'}: raise ValueError('原文核对输入含未知字段')
    from .review_io import instant
    cutoff=instant(spec['asOf']) if spec.get('asOf') is not None else None
    sources = spec.get('sources'); claims = spec.get('claims')
    if not isinstance(sources,list) or not 1 <= len(sources) <= 100: raise ValueError('需1至100项原始资料')
    if not isinstance(claims,list) or not 1 <= len(claims) <= 100: raise ValueError('需1至100条主张')
    rows=[]; ids=set(); texts={}; groups={}; all_pages={};text_groups={};input_bytes=0
    if verify_urls and len(sources)>10:raise ValueError('一次显式联网核对最多10项来源，其他资料可分批核对')
    for source in sources:
        if not isinstance(source,dict): raise ValueError('资料须为对象')
        if set(source)-{'id','file','expectedSha256','sourceUrl','publishedAt','page','excerpt','title','sourceVersion','subjectId','sourceType','requiredAttachments'}:raise ValueError('来源输入含未知字段；不能填写程序生成的核查结果')
        sid=source.get('id')
        if not isinstance(sid,str) or not sid.strip() or sid in ids: raise ValueError('资料ID须非空且唯一')
        ids.add(sid)
        if not isinstance(source.get('file'),str) or not source['file'].strip(): raise ValueError('须明确指定原文件路径')
        expected=source.get('expectedSha256')
        if expected is not None and (not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected)): raise ValueError('声明摘要须为64位小写十六进制，未知留空')
        if source.get('excerpt') is not None and (not isinstance(source['excerpt'],str) or len(source['excerpt'])>20000): raise ValueError('摘录须为文字，最多20000字符')
        row=dict(source, sourceRead=False, publisherAuthenticated=False, semanticVerification='not-performed')
        try:
            path=Path(source.get('file','')); path=path if path.is_absolute() else base/path
            input_bytes+=path.stat().st_size
            if input_bytes>64*1024*1024:raise ValueError('本次所选原文件总量超过64MiB，余项保留未读取，请分批核对')
            sha,pages=artifact(path); row.update(sourceRead=True, actualSha256=sha, pageCount=len(pages))
            all_pages[sid]=pages
            expected=source.get('expectedSha256'); row['hashMatch']=None if expected is None else sha==expected
            page=source.get('page'); excerpt=source.get('excerpt')
            if page is not None and (type(page) is not int or not 1 <= page <= len(pages)):
                row.update(locatorVerified=False, excerptFound=False, reason='页码超出实际文件范围')
            else:
                selected=pages[page-1] if page is not None else '\n'.join(pages)
                found=isinstance(excerpt,str) and bool(excerpt.strip()) and excerpt in selected
                row.update(locatorVerified=found if page is not None else None, excerptFound=found,
                           reason='摘录逐字匹配' if found else '未找到逐字摘录；扫描PDF或排版差异也可能导致失败，不自动判定伪造')
                texts[sid]=selected
            groups.setdefault(sha,[]).append(sid)
            enrich_source(row,pages,base,verify_urls,cutoff)
            if row['normalizedTextSha256']:text_groups.setdefault(row['normalizedTextSha256'],[]).append(sid)
        except (OSError,ValueError,UnicodeError,TypeError) as error:
            row.update(reason=str(error), excerptFound=False, locatorVerified=False)
        rows.append(row)
    relations,searches=links_and_search(spec,rows)
    for row in rows:
        row['registeredAttachments']=[rel['from'] for rel in relations if rel['type']=='attachment' and rel['to']==row['id']]
        required=row.get('requiredAttachments',[])
        if not isinstance(required,list) or len(required)>100 or any(not isinstance(s,str) or not s.strip() or s==row['id'] for s in required) or len(set(required))!=len(required):raise ValueError('必需附件须为至多100个不重复的其他资料ID；未取得的ID可保留')
        available=[sid for sid in required if sid in row['registeredAttachments'] and any(r['id']==sid and r['sourceRead'] and r.get('hashMatch') is not False and any(p.strip() for p in all_pages.get(sid,[])) for r in rows)]
        row['attachmentCoverage']=dict(required=required,available=available,missing=[sid for sid in required if sid not in available],scope='仅核声明必需附件的登记、读取和摘要；不认证附件完整性或表格布局')
    claim_rows=[]; seen=set()
    for claim in claims:
        if not isinstance(claim,dict): raise ValueError('主张须为对象')
        if set(claim)-{'id','text','links','checks'}:raise ValueError('主张输入含未知字段；核查结果由程序生成')
        cid=claim.get('id'); text=claim.get('text')
        if not isinstance(cid,str) or not cid.strip() or cid in seen or not isinstance(text,str) or not text.strip(): raise ValueError('主张ID须唯一，文字不能为空')
        seen.add(cid); links=claim.get('links',[])
        if not isinstance(links,list): raise ValueError('links须为列表')
        linked=set()
        for link in links:
            if not isinstance(link,dict): raise ValueError('关联须为对象')
            if set(link)!={'sourceId','relation','rationale'}:raise ValueError('关联仅接受sourceId、relation、rationale；不能伪填程序认证字段')
            if not isinstance(link.get('sourceId'),str) or link['sourceId'] not in ids or link['sourceId'] in linked: raise ValueError('关联资料不存在或重复')
            linked.add(link['sourceId'])
            if link.get('relation') not in ('supports','contradicts','partial','context'): raise ValueError('关联关系无效')
            if not isinstance(link.get('rationale'),str) or not link['rationale'].strip(): raise ValueError('须填写关联理由')
        claim_rows.append(dict(claim, alerts=alerts(text), relationSemanticsVerified=False,
                               reviewProgress='待逐项语义复核', status='材料检查完成，不代表主张证实',aspectChecks=aspects(claim,rows,all_pages)))
        checks=claim_rows[-1]['aspectChecks']
        if checks:claim_rows[-1]['reviewProgress']=str(sum(c['effectiveFinding']!='unknown' for c in checks))+'项已有复核声明，'+str(sum(c['effectiveFinding']=='unknown' for c in checks))+'项仍未知；语义与复核身份未认证'
        opinions=[]
        for finding,label in [('contradicts','有反对意见'),('supports','有支持意见'),('partial','只有局部支持'),('unknown','仍未知')]:
            names=list(dict.fromkeys(ASPECTS[c['aspect']] for c in checks if c['effectiveFinding']==finding))
            if names:opinions.append('、'.join(names)+label)
        claim_rows[-1]['declaredJudgment']='按复核声明：'+'；'.join(opinions)+'。仅限所核对象与范围，不是整体真实性认证。' if opinions else '尚未登记逐项语义复核，不能由文件匹配确认整条消息。'
    from .announcement_review import review as announcements
    metrics=announcements(spec.get('announcementMetrics',[]),ids)
    bindings=spec.get('metricBindings',[])
    if not isinstance(bindings,list) or len(bindings)>500:raise ValueError('指标关联最多500项')
    pairs=set();metric_ids={m['id'] for m in metrics}
    for binding in bindings:
        if not isinstance(binding,dict) or set(binding)!={'claimId','metricId','rationale'}:raise ValueError('指标关联须明确claimId、metricId和rationale')
        if not isinstance(binding['claimId'],str) or binding['claimId'] not in seen or not isinstance(binding['metricId'],str) or binding['metricId'] not in metric_ids:raise ValueError('指标关联引用的主张或指标不存在')
        pair=(binding['claimId'],binding['metricId'])
        if pair in pairs or not isinstance(binding['rationale'],str) or not binding['rationale'].strip():raise ValueError('指标关联不得重复，且须给出依据')
        pairs.add(pair)
    from decimal import Decimal,localcontext
    import unicodedata
    for metric in metrics:
        quote=metric.get('evidenceExcerpt')
        if quote is not None and (not isinstance(quote,str) or not quote.strip() or len(quote)>20000):raise ValueError('指标摘录须为非空文字，最多20000字符')
        from .evidence_details import context as quote_context
        source_row=next(r for r in rows if r['id']==metric['sourceId'])
        evidence_page=metric.get('evidencePage',source_row.get('page'))
        locations=quote_context(all_pages.get(metric['sourceId'],[]),quote,evidence_page)
        matched=bool(locations)
        mentions=[]
        if matched:
            for match in re.finditer(r'(?<![A-Za-z0-9_.])(-?\d[\d,]*(?:\.\d+)?)\s*(亿元|万元|元|亿|万)',unicodedata.normalize('NFKC',quote)):
                if len(match.group(1).replace(',',''))>100:continue
                factor={'元':Decimal(1),'万':Decimal(10000),'万元':Decimal(10000),'亿':Decimal(100000000),'亿元':Decimal(100000000)}[match.group(2)]
                with localcontext() as context:
                    context.prec=220
                    mentions.append(str(Decimal(match.group(1).replace(',',''))*factor))
        checks={key:None if value is None or not mentions else any(Decimal(value)==Decimal(n) for n in mentions) for key,value in metric['normalized'].items()}
        source_usable=source_row['sourceRead'] and source_row.get('hashMatch') is not False and not source_row.get('timeCheck',{}).get('futurePublication') and source_row.get('timeCheck',{}).get('precision')!='invalid'
        if source_row.get('timeCheck',{}).get('cutoffRequested'):source_usable=source_usable and source_row['timeCheck']['availableAtCutoff'] is True
        if source_row.get('urlCheck',{}).get('requested'):source_usable=source_usable and source_row['urlCheck'].get('bytesMatch') is True
        metric['sourceEvidenceCheck']=dict(excerpt=quote,excerptMatched=matched,evidencePage=evidence_page,matchedContexts=locations,sourceChecksPassed=bool(source_usable),numericMentionMatch=checks,scope='页码指提取页；来源检查通过不认证来源身份；只比逐字摘录和显式数字与单位，不认证表格列、脚注对应、指标、主体、币种、审计状态或语义；亏损文字与括号等需另核')
        if not source_usable:metric['warnings'].append('指标来源的读取、摘要、联网对应或截止条件存在缺口，数字命中不代表证据可用')
        if not matched:metric['warnings'].append('指标没有匹配的专属原文摘录，金额与口径仍为声明，比较仅按输入暂算')
        elif not mentions:metric['warnings'].append('摘录未给出可识别的显式金额与单位，需核对指标原句')
        elif any(value is False for value in checks.values()):metric['warnings'].append('声明数值未匹配专属摘录中的显式金额，先核对原单位、正负号和指标')
    human=[]
    for binding in bindings:human.append(('指标与主张关联',binding['claimId']+' ← '+binding['metricId']+'；'+binding['rationale']+'；输入者声明关联，不认证指标语义'))
    for metric in metrics:
        values=metric['normalized']; labels={'value':'声明值','lower':'声明区间下限','upper':'声明区间上限'}
        from decimal import Decimal
        description='；'.join(labels[k]+'：'+('未知' if v is None else format(Decimal(v),',f')+'元（'+metric['currency']+'）') for k,v in values.items())
        human.append((metric['subject']+' · '+metric['metric']+' · '+metric['disclosureType'],description+'；原单位：'+metric['unit']+'；'+metric['auditStatus']+'；'+metric['basis']+'；'+metric['periodStart']+'至'+metric['periodEnd']))
        human.append(('公告数值核查范围','以上金额、审计和口径来自输入声明；比较结果仅为按声明数值暂算，未认证原文指标对应关系。'))
        if metric.get('evidenceExcerpt'):human.append(('指标专属原句',metric['evidenceExcerpt']+'；逐字匹配：'+('是' if metric['sourceEvidenceCheck']['excerptMatched'] else '否')+'；数字命中不等于指标认证'))
        for hit in metric['sourceEvidenceCheck']['matchedContexts'][:3]:human.append(('指标原句位置与上下文','来源：'+metric['sourceId']+'；提取页'+str(hit['page'])+'；偏移'+str(hit['offset'])+'；'+hit['before']+'【指标原句】'+hit['excerpt']+'【后文】'+hit['after']+'；不认证表格列或脚注对应'))
        for warning in metric['warnings']: human.append(('公告核对提示',warning))
        if 'versionDifference' in metric: human.append(('版本差额',metric['versionDifference']+'；'+metric['differenceMeaning']))
    for row in rows:
        human.append((row['id'], '读取成功' if row['sourceRead'] else '读取失败：'+row['reason']))
        human.append((row['id']+' · 来源地址',str(row.get('sourceUrl') or '未知')+'；'+str(row.get('urlCheck',{}).get('reason','文件未读取，地址与文件对应关系未核'))))
        if row.get('urlCheck',{}).get('status')=='visited':human.append((row['id']+' · 实际访问比较','下载字节与当前文件'+('一致' if row['urlCheck']['bytesMatch'] else '不一致')+'；仍不认证发布者与内容'))
        human.append((row['id']+' · 核查范围','文件读取不证明内容真实；发布者未认证，语义未自动复核，附件及表格布局未核'))
        if row['attachmentCoverage']['required']:human.append((row['id']+' · 必需附件','已登记且读取：'+str(row['attachmentCoverage']['available'])+'；缺失或未通过摘要：'+str(row['attachmentCoverage']['missing'])+'；'+row['attachmentCoverage']['scope']))
        human.append((row['id']+' · 披露时间',row.get('timeCheck',{}).get('reason','未知')))
        if cutoff:human.append((row['id']+' · 截止可用性','按声明时间：'+{True:'截止前可用',False:'截止后才可用',None:'不能确定'}[row.get('timeCheck',{}).get('availableAtCutoff')]+'；不认证首次披露时间'))
        human.append((row['id']+' · 原文摘录',row.get('excerpt') or '未提供摘录'))
        human.append((row['id']+' · 摘录与定位',row['reason']+'；摘要比较：'+('未提供声明摘要' if row.get('hashMatch') is None else '一致' if row['hashMatch'] else '不一致，请核对原文件或版本')))
        for hit in row.get('contexts',[]):human.append((row['id']+' · 提取页'+str(hit['page'])+'上下文',hit['before']+'【摘录】'+hit['excerpt']+'【后文】'+hit['after']))
        warning_groups={}
        for warning in row.get('fullTextAlerts',[]):warning_groups.setdefault((warning['page'],warning['code']),[]).append(warning)
        for (page,code),warnings in warning_groups.items():
            matched='、'.join(dict.fromkeys(w['matched'] for w in warnings))
            content=all_pages.get(row['id'],[''])[page-1];spans=[]
            for w in sorted(warnings,key=lambda x:x['offset']):
                start=max(0,w['offset']-60);end=min(len(content),w['offset']+len(w['matched'])+100)
                if spans and start<=spans[-1][1]:spans[-1][1]=max(spans[-1][1],end)
                else:spans.append([start,end])
            contexts=' / '.join(content[start:end] for start,end in spans)
            human.append((row['id']+' · 全文提示 / 提取页'+str(page),'命中：'+matched+'；'+warnings[0]['question']+'；上下文：'+contexts+'；可能误报或漏报'))
        if row.get('extractionCoverage',{}).get('emptyPages'):human.append((row['id']+' · 提取缺口','以下页无可提取文本，不能当作完整核查：'+str(row['extractionCoverage']['emptyPages'])))
    human.append(('文件分组',str(len(groups))+'个实际字节摘要组；'+str(len(text_groups))+'个规范化文本组。分组不证明来源独立；相同文本仅提示疑似重复。'))
    for group in text_groups.values():
        if len(group)>1:human.append(('疑似重复文本','、'.join(group)+'；只统一空白，保留各原文件摘要，不增加独立支持'))
    relation_names={'reprint':'转载','progress':'后续进展','correction':'更正','denial':'否认','attachment':'附件','independent-check':'独立验证声明'}
    for relation in relations:human.append(('来源链',relation['from']+' → '+relation['to']+'；'+relation_names[relation['type']]+'；'+relation['reason']+'；关系由输入者声明'))
    search_names={'not-searched':'尚未查找','searched-no-find':'已查所列范围，未找到','found':'找到所列资料','unavailable':'来源无法访问'}
    for search in searches:human.append(('反证查找记录',search['query']+'；范围：'+search['scope']+'；'+search_names[search['status']]+'；'+search['reason']+'；查找过程为声明，未找到不等于没有反证'))
    for claim in claim_rows:
        human.append((claim['text']+' · 本轮判断',claim['declaredJudgment']))
        human.append((claim['text'],claim['status']+'；'+claim['reviewProgress']))
        for check in claim['aspectChecks']:
            human.append((claim['text']+' · '+ASPECTS[check['aspect']],check['expected']+'；原句：'+(check['excerpt'] or '未知')+'；复核意见：'+{'supports':'声明支持','contradicts':'声明反对','partial':'局部支持','unknown':'尚未确认'}[check['effectiveFinding']]+'；'+check['rationale']+'；'+check['reason']))
            human.append(('逐项复核声明记录','声明者：'+str(check['reviewer'] or '未知')+'；声明时间：'+str(check['reviewedAt'] or '未知')+'；程序未认证身份或实际复核行为'))
            for hit in check['matchedContexts'][:3]:human.append(('逐项原句位置与上下文','来源：'+str(check['sourceId'])+'；提取页'+str(hit['page'])+'；偏移'+str(hit['offset'])+'；'+hit['before']+'【核对原句】'+hit['excerpt']+'【后文】'+hit['after']))
        for warning in claim['alerts']: human.append((claim['text']+' · 措辞核对',warning['question']))
        for link in claim.get('links',[]):
            human.append((claim['text']+' · '+link['sourceId'],{'supports':'声明支持','contradicts':'声明反对','partial':'局部支持','context':'背景资料'}[link['relation']]+'；'+link['rationale']))
            source=next(s for s in rows if s['id']==link['sourceId'])
            for warning in alerts(source.get('excerpt') or ''):
                human.append((link['sourceId']+' · 原文措辞核对',warning['question']+'触发文字：'+','.join(warning['matched'])+'；不自动改变关系。'))
            if not source.get('excerptFound') or source.get('hashMatch') is False:
                human.append((claim['text']+' · 原文件缺口','关联资料的摘录或摘要未通过核对，此关联仍为输入者声明，不能按已核原文使用。'))
    plan=spec.get('researchPlan',{})
    if not isinstance(plan,dict) or set(plan)-{'priorityQuestions','stopWhen','remainingQuestions'} or any(not isinstance(v,list) or any(not isinstance(x,str) or not x.strip() for x in v) for v in plan.values()):raise ValueError('研究计划须为问题列表、停止条件列表和剩余问题列表')
    for key,label in [('priorityQuestions','优先核查'),('stopWhen','本轮停止条件'),('remainingQuestions','下一步关键缺口')]:
        for question in plan.get(key,[]):human.append((label,question+'；计划与达成情况需分别核对'))
    declared=[c for c in claim_rows if c['aspectChecks']]
    summary=dict(fileChecks='读取'+str(sum(r['sourceRead'] for r in rows))+'/'+str(len(rows))+'项；不代表内容真实',confirmedScope='本次'+str(sum(bool(r.get('excerptFound')) for r in rows))+'项逐字摘录匹配；'+str(sum(r.get('hashMatch') is False for r in rows))+'项摘要不一致。语义意见均为复核声明',cannotConfirm='发布者真实性、实际履约、身份认证与完整附件尚未由程序确认',reviewedClaims=len(declared),counterevidenceSearch='有声明查找记录' if searches else '未登记反证查找，不得称无反证',nextSteps=plan.get('remainingQuestions',[]) or ['核对关键主张的主体、动作、金额、期间、阶段及否认范围'])
    priority=[row for row in human if any(row[0]==c['text'] or row[0].startswith(c['text']+' · ') for c in claim_rows) or row[0].endswith(' · 来源地址')]
    human=[row for row in human if row not in priority]
    judgments=[row for row in priority if row[0].endswith(' · 本轮判断')]
    human[:0]=judgments+[('本轮能够确认',summary['confirmedScope']),('本轮不能确认',summary['cannotConfirm']),('反证查找范围',summary['counterevidenceSearch']),('下一步','；'.join(summary['nextSteps']))]+[row for row in priority if row not in judgments]
    return dict(methodVersion=spec['inputSchema'],conclusion=summary['fileChecks']+'。核对匹配不等于证实；逐项复核声明、反证范围和剩余问题见正文。',
                sources=rows,claims=claim_rows,announcementMetrics=metrics,metricBindings=bindings,artifactGroups=list(groups.values()),normalizedTextGroups=list(text_groups.values()),sourceRelations=relations,searchLog=searches,researchPlan=plan,answerSummary=summary,humanRows=human,
                limitations=['文件读取和摘要一致不认证发布机构、真实披露时间或内容真实性。','不同文件摘要不证明来源独立；转载和通稿需追溯共同出处。','核查支持、反证及后续更正；未找到反证不等于消息真实。','PDF只提取文本，不做OCR；匹配失败保留原因。','默认仅核本地文件；只有显式verify-urls才联网，不执行原文指令、不复制原文件进入发布包。'])

def main(argv=None):
    p=argparse.ArgumentParser(description='独立原文核对：明确选择文件，不认证消息真伪')
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('scaffold'); s.add_argument('--source',type=Path,required=True); s.add_argument('--out',type=Path,required=True)
    s.add_argument('--claim',default='填写要核对的具体主张'); s.add_argument('--excerpt')
    f=sub.add_parser('fetch'); f.add_argument('--url',required=True); f.add_argument('--out-dir',type=Path,required=True)
    r=sub.add_parser('review'); r.add_argument('--input',type=Path,required=True); r.add_argument('--out-dir',type=Path,required=True)
    r.add_argument('--verify-urls',action='store_true',help='显式访问所填公开HTTPS地址并比较字节；最多10项，不认证发布者')
    c=sub.add_parser('compare');c.add_argument('--previous',type=Path,required=True);c.add_argument('--current',type=Path,required=True);c.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        if a.command=='fetch':
            from .source_fetch import fetch
            from datetime import datetime, timezone
            if a.out_dir.exists(): raise ValueError('输出目录已存在，旧文件保留')
            body,metadata=fetch(a.url)
            metadata.update(requestedUrl=a.url,retrievedAt=datetime.now(timezone.utc).isoformat(),rawSha256=hashlib.sha256(body).hexdigest())
            import os,tempfile,shutil
            a.out_dir.parent.mkdir(parents=True,exist_ok=True)
            stage=Path(tempfile.mkdtemp(prefix='.source-',dir=a.out_dir.parent))
            try:
                suffix='.pdf' if body.startswith(b'%PDF') else '.html' if 'html' in (metadata.get('contentType') or '') else '.txt'
                (stage/('original'+suffix)).write_bytes(body)
                (stage/'receipt.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
                os.rename(stage,a.out_dir)
            finally:
                if stage.exists(): shutil.rmtree(stage)
            print('原文件已取得，来源身份与内容仍待核查：'+str(a.out_dir))
        elif a.command=='scaffold':
            sha,pages=artifact(a.source)
            spec=dict(inputSchema='source-review/2',sources=[dict(id='source-1',file=str(a.source.resolve()),expectedSha256=sha,sourceUrl=None,publishedAt=None,page=None,excerpt=a.excerpt)],claims=[dict(id='claim-1',text=a.claim,links=[],checks=[])],sourceRelations=[],searchLog=[],researchPlan=dict(priorityQuestions=[],stopWhen=[],remainingQuestions=[]))
            with a.out.open('x',encoding='utf-8') as f: json.dump(spec,f,ensure_ascii=False,indent=2)
            print('模板已生成：请填写主张、摘录、来源和日期；未知保留空值。')
        elif a.command=='compare':
            if a.out_dir.exists():raise ValueError('输出目录已存在，历史结果不覆盖')
            from .evidence_compare import compare
            spec=dict(previous=read(a.previous),current=read(a.current));result=compare(spec['previous'],spec['current'])
            out=publish(spec,result,a.out_dir,'市场明镜：证据版本变化');print('对比报告已生成：'+str(out/'report.html'))
        else:
            print('进度 1/3：读取输入与明确选定的原文件')
            if a.out_dir.exists():raise ValueError('输出目录已存在，历史结果不覆盖')
            spec=read(a.input)
            result=review(spec,a.input.resolve().parent,a.verify_urls)
            print('进度 2/3：核对摘要、摘录、页码和措辞风险')
            out=publish(spec,result,a.out_dir,'市场明镜：原始资料核对')
            print('进度 3/3：报告已保存：'+str(out/'report.html'))
        return 0
    except (OSError,ValueError,UnicodeError) as error:
        print('未完成：'+str(error)); return 2

if __name__=='__main__': raise SystemExit(main())
