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

LIMIT = 16 * 1024 * 1024

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('p', 'br', 'div', 'li', 'tr'): self.parts.append('\n')
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
        pages = [p.extract_text() or '' for p in reader.pages]
    else:
        content = raw.decode('utf-8-sig')
        if path.suffix.lower() in ('.html', '.htm'):
            parser = VisibleText(); parser.feed(content); content = ''.join(parser.parts)
        elif path.suffix.lower() not in ('.txt', '.md', '.csv'):
            raise ValueError('支持UTF-8文本、HTML及可选PDF；不执行文件内容')
        pages = [content]
    return hashlib.sha256(raw).hexdigest(), pages

def alerts(text):
    groups = [
        ('uncertain', ('据传','传闻','或将','拟','有望','疑似','有消息称'), '核对支持的是传闻存在、计划发布还是实际执行。'),
        ('actor-boundary', ('国家队','主力','机构','游资','庄家','北向','央企','国资'), '说明具体主体、统计范围和识别依据；集体名称或所有制不证明动作与动机。'),
        ('absolute-or-trade', ('必然','一定','百分之百','满仓','翻倍','必涨'), '核对是否为引用、否定或保证性表述；工具不背书收益保证和交易建议。'),
        ('stage-check', ('尚未','未实施','拟','否认','澄清','更正','终止'), '逐项对照动作和阶段；否认与更正不能替代全部历史。')]
    return [dict(code=code, matched=[w for w in words if w in text], question=question,
                 scope='关键词提示可能误报或漏报，不自动改变证据关系')
            for code, words, question in groups if any(w in text for w in words)]

def review(spec, base):
    if not isinstance(spec, dict) or spec.get('inputSchema') != 'source-review/1': raise ValueError('须为source-review/1')
    if set(spec)-{'inputSchema','sources','claims','announcementMetrics'}: raise ValueError('原文核对输入含未知字段')
    sources = spec.get('sources'); claims = spec.get('claims')
    if not isinstance(sources,list) or not 1 <= len(sources) <= 100: raise ValueError('需1至100项原始资料')
    if not isinstance(claims,list) or not 1 <= len(claims) <= 100: raise ValueError('需1至100条主张')
    rows=[]; ids=set(); texts={}; groups={}
    for source in sources:
        if not isinstance(source,dict): raise ValueError('资料须为对象')
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
            sha,pages=artifact(path); row.update(sourceRead=True, actualSha256=sha, pageCount=len(pages))
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
        except (OSError,ValueError,UnicodeError,TypeError) as error:
            row.update(reason=str(error), excerptFound=False, locatorVerified=False)
        rows.append(row)
    claim_rows=[]; seen=set()
    for claim in claims:
        if not isinstance(claim,dict): raise ValueError('主张须为对象')
        cid=claim.get('id'); text=claim.get('text')
        if not isinstance(cid,str) or not cid.strip() or cid in seen or not isinstance(text,str) or not text.strip(): raise ValueError('主张ID须唯一，文字不能为空')
        seen.add(cid); links=claim.get('links',[])
        if not isinstance(links,list): raise ValueError('links须为列表')
        linked=set()
        for link in links:
            if not isinstance(link,dict): raise ValueError('关联须为对象')
            if link.get('sourceId') not in ids or link['sourceId'] in linked: raise ValueError('关联资料不存在或重复')
            linked.add(link['sourceId'])
            if link.get('relation') not in ('supports','contradicts','partial','context'): raise ValueError('关联关系无效')
            if not isinstance(link.get('rationale'),str) or not link['rationale'].strip(): raise ValueError('须填写关联理由')
        claim_rows.append(dict(claim, alerts=alerts(text), relationSemanticsVerified=False,
                               reviewProgress='待逐项语义复核', status='材料检查完成，不代表主张证实'))
    from .announcement_review import review as announcements
    metrics=announcements(spec.get('announcementMetrics',[]),ids)
    human=[]
    for metric in metrics:
        values=metric['normalized']; labels={'value':'披露值','lower':'区间下限','upper':'区间上限'}
        description='；'.join(labels[k]+'：'+('未知' if v is None else v+'元（'+metric['currency']+'）') for k,v in values.items())
        human.append((metric['subject']+' · '+metric['metric']+' · '+metric['disclosureType'],description+'；原单位：'+metric['unit']+'；'+metric['auditStatus']+'；'+metric['basis']+'；'+metric['periodStart']+'至'+metric['periodEnd']))
        for warning in metric['warnings']: human.append(('公告核对提示',warning))
        if 'versionDifference' in metric: human.append(('版本差额',metric['versionDifference']+'；'+metric['differenceMeaning']))
    for row in rows:
        human.append((row['id'], '读取成功' if row['sourceRead'] else '读取失败：'+row['reason']))
        human.append((row['id']+' · 原文摘录',row.get('excerpt') or '未提供摘录'))
        human.append((row['id']+' · 摘录与定位',row['reason']+'；摘要比较：'+('未提供声明摘要' if row.get('hashMatch') is None else '一致' if row['hashMatch'] else '不一致，请核对原文件或版本')))
    for claim in claim_rows:
        human.append((claim['text'],claim['reviewProgress']))
        for warning in claim['alerts']: human.append((claim['text']+' · 措辞核对',warning['question']))
        for link in claim.get('links',[]):
            human.append((claim['text']+' · '+link['sourceId'],{'supports':'声明支持','contradicts':'声明反对','partial':'局部支持','context':'背景资料'}[link['relation']]+'；'+link['rationale']))
            source=next(s for s in rows if s['id']==link['sourceId'])
            for warning in alerts(source.get('excerpt') or ''):
                human.append((link['sourceId']+' · 原文措辞核对',warning['question']+'触发文字：'+','.join(warning['matched'])+'；不自动改变关系。'))
            if not source.get('excerptFound') or source.get('hashMatch') is False:
                human.append((claim['text']+' · 原文件缺口','关联资料的摘录或摘要未通过核对，此关联仍为输入者声明，不能按已核原文使用。'))
    return dict(methodVersion='source-review/1',conclusion='实际读取所选文件并核对摘要、摘录及页码；发布者身份、原文语义和主张真伪仍未认证。',
                sources=rows,claims=claim_rows,announcementMetrics=metrics,artifactGroups=list(groups.values()),humanRows=human,
                limitations=['文件读取和摘要一致不认证发布机构、真实披露时间或内容真实性。','不同文件摘要不证明来源独立；转载和通稿需追溯共同出处。','核查支持、反证及后续更正；未找到反证不等于消息真实。','PDF只提取文本，不做OCR；匹配失败保留原因。','本流程不联网、不执行原文指令、不复制原文件进入发布包。'])

def main(argv=None):
    p=argparse.ArgumentParser(description='独立原文核对：明确选择文件，不认证消息真伪')
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('scaffold'); s.add_argument('--source',type=Path,required=True); s.add_argument('--out',type=Path,required=True)
    s.add_argument('--claim',default='填写要核对的具体主张'); s.add_argument('--excerpt')
    f=sub.add_parser('fetch'); f.add_argument('--url',required=True); f.add_argument('--out-dir',type=Path,required=True)
    r=sub.add_parser('review'); r.add_argument('--input',type=Path,required=True); r.add_argument('--out-dir',type=Path,required=True)
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
            spec=dict(inputSchema='source-review/1',sources=[dict(id='source-1',file=str(a.source.resolve()),expectedSha256=sha,sourceUrl=None,publishedAt=None,page=None,excerpt=a.excerpt)],claims=[dict(id='claim-1',text=a.claim,links=[])])
            with a.out.open('x',encoding='utf-8') as f: json.dump(spec,f,ensure_ascii=False,indent=2)
            print('模板已生成：请填写主张、摘录、来源和日期；未知保留空值。')
        else:
            print('进度 1/3：读取输入与明确选定的原文件')
            result=review(read(a.input),a.input.resolve().parent)
            print('进度 2/3：核对摘要、摘录、页码和措辞风险')
            out=publish(read(a.input),result,a.out_dir,'市场明镜：原始资料核对')
            print('进度 3/3：报告已保存：'+str(out/'report.html'))
        return 0
    except (OSError,ValueError,UnicodeError) as error:
        print('未完成：'+str(error)); return 2

if __name__=='__main__': raise SystemExit(main())
