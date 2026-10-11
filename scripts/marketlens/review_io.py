# SPDX-License-Identifier: MIT
"""Original standalone research report I/O, no mandatory shared installation."""
import argparse,json,hashlib,os,tempfile,shutil,sys
from pathlib import Path
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
from html import escape

def day(value):
    if not isinstance(value,str) or len(value)!=10:raise ValueError('日期须YYYY-MM-DD')
    return date.fromisoformat(value)

def instant(value):
    if not isinstance(value,str):raise ValueError('取得/截止时间须含时区')
    try: d=datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,TypeError,AttributeError): raise ValueError('时间须为ISO格式，例如2026-10-10T20:00:00+08:00')
    if d.tzinfo is None:raise ValueError('时间须含时区')
    return d

def number(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float)):raise ValueError('金额须明确有限数值')
    try:n=Decimal(str(value))
    except InvalidOperation as e:raise ValueError('金额无效') from e
    if not n.is_finite():raise ValueError('金额非有限')
    return n

def evidence(row,cutoff):
    if not isinstance(row,dict) or not isinstance(row.get('source'),str) or not row['source'].startswith('https://') or not row.get('locator') or not row.get('sourceVersion'):raise ValueError('资料须明确HTTPS来源、定位及版本')
    published=day(row['publishedDate']);acquired=instant(row['acquiredAt'])
    if published>acquired.astimezone(timezone(timedelta(hours=8))).date():raise ValueError('取得早于发布日期')
    sha=row.get('rawSourceSha256')
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('需原始来源摘要，摘要不认证原文')
    return acquired<=instant(cutoff) and published<=instant(cutoff).astimezone(timezone(timedelta(hours=8))).date()

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()

def pairs(items):
    out={}
    for k,v in items:
        if k in out:raise ValueError('JSON字段重复：'+k)
        out[k]=v
    return out

def read(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>16*1024*1024:raise ValueError('输入不存在、链接或超过16MiB')
    return json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('非有限JSON')))

def render(result,title):
    summary=result.get('conclusion','结果按所填资料范围生成；先核对下方依据与缺口。')
    if result.get('methodVersion')=='claim-evidence/1':
        summary='以下关系仅由输入者声明；本流程未读取原始文件或认证来源、语义及消息真伪。旧接口计数保留在底稿，不能当作已核结论。'
    lines=result.get('humanRows',[])
    table='<table><tr><th>核对项</th><th>本次结果</th></tr>'+''.join('<tr><td>'+escape(str(a))+'</td><td>'+escape(str(b))+'</td></tr>' for a,b in lines)+'</table>' if lines else ''
    gaps='<ul>'+''.join('<li>'+escape(str(s))+'</li>' for s in result.get('limitations',[]))+'</ul>'
    labels={'declared-support':'有声明直接支持','declared-counterevidence':'有声明反对材料','partial-only':'只有局部支持','context-only':'只有背景资料','conflicting':'支持与反对材料冲突','insufficient':'缺少可纳入证据'}
    records=result.get('records',[])
    counts={k:sum(isinstance(r,dict) and r.get('status')==k for r in records) for k in labels}
    cards=''
    if any(counts.values()):
        cards='<h2>主张的证据状态</h2><p>数量是主张分类，不是可信度、胜率或来源独立性。</p><div class="cards">'+''.join('<div class="card '+('gap' if k in ('partial-only','context-only') else 'conflict' if k=='conflicting' else '')+'"><strong>'+escape(v)+'</strong><div>'+str(counts[k])+' 条</div></div>' for k,v in labels.items())+'</div>'
    structured=[];pending=[];evidence_rows=[]
    for record in records:
        if not isinstance(record,dict): continue
        groups=record.get('sourceArtifactGroups',[])
        evidence_rows.append((record.get('text','主张'),f"纳入{len(record.get('admitted',[]))}项，按声明摘要分为{len(groups)}组；未认证来源独立性"))
        for kind in ('admitted','excluded'):
            for link in record.get(kind,[]):
                evidence_rows.append((str(link.get('evidenceId'))+' · '+('纳入' if kind=='admitted' else '未纳入'),str(link.get('source'))+'；定位：'+str(link.get('locator'))+'；声明关系：'+str(link.get('relation'))+'；理由：'+str(link.get('rationale'))+'；排除原因：'+str(link.get('exclusion','无'))))
                evidence_rows.append((str(link.get('evidenceId'))+' · 原文摘录',link.get('excerpt') or '摘录未知'))
                if link.get('binding'): evidence_rows.append((str(link.get('evidenceId'))+' · 复核声明',json.dumps(link['binding'],ensure_ascii=False)+'；人员身份与实际复核行为未认证'))
        from .source_review import alerts
        for warning in alerts(record.get('text','')): evidence_rows.append(('措辞提示：'+str(warning['matched']),warning['question']+'关键词可能误报或漏报，不自动改判。'))
    for r in records:
        if not isinstance(r,dict):continue
        if isinstance(r.get('argument'),dict):
            for key,label in [('warrant','推理依据'),('qualifier','适用限定'),('falsifier','推翻条件')]:
                field=r['argument'][key];structured.append((r['text']+' · '+label,field['text'] if field['text'] is not None else '未知：'+str(field['reason'])))
        for link in r.get('proposedOrDeferredLinks',[]):
            pending.append((r['id']+' / '+link['evidenceId'],{'supports':'声明支持','contradicts':'声明反对','partial':'局部支持','context':'背景'}[link['relation']]+'；'+{'proposal-not-reviewed':'建议未复核','binding-after-cutoff':'关联晚于截止时点'}[link['exclusion']]+'；提出者：'+link['binding']['proposedBy']))
    def rows_table(items,heading):
        return '<h2>'+heading+'</h2><table>'+''.join('<tr><td>'+escape(str(a))+'</td><td>'+escape(str(b))+'</td></tr>' for a,b in items)+'</table>' if items else ''
    argument_html=rows_table(evidence_rows,'原文、关联与复核记录')+rows_table(structured,'声明的论证与未知事项')+rows_table(pending,'建议及未纳入的关联')
    notice='<aside role="note"><strong>计算已完成，证据仍需复查</strong><p>报告生成成功只表示所填输入通过本流程。请先看结论适用范围，再核对来源、期间、版本与排除项；缺口不能当作零。</p></aside>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{max-width:960px;margin:32px auto;padding:0 20px;font:17px/1.7 system-ui;color:#203047}aside{padding:12px 16px;background:#f2f5fa;border-left:4px solid #48658b}td,th{padding:10px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}table{width:100%;table-layout:fixed}th:first-child,td:first-child{width:28%}td{vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin-top:24px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}.card{padding:12px;border:1px solid #d9e2ec;border-radius:8px;background:#f4f7fa}.gap{background:#fff4d8;border-color:#e8c971}.conflict{background:#fff0ed}</style><h1>'+escape(title)+'</h1><p>'+escape(summary)+'</p>'+cards+notice+table+argument_html+'<h2>范围与缺口</h2>'+gaps+'<details><summary>完整输入绑定、结果及依据</summary><pre>'+escape(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))+'</pre></details></html>'

def publish(spec,result,out,title):
    out=Path(out).absolute()
    if out.exists() or out.is_symlink():raise ValueError('输出必须是新目录，历史结果不覆盖')
    out.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.research-',dir=out.parent))
    try:
        result=dict(result,inputSha256=digest(spec),methodVersion=result.get('methodVersion','explicit-research-review/1.0'),executionStatus='completed',evidenceCertification='not-performed-by-report-writer')
        for name,data in [('input.json',spec),('result.json',result)]: (stage/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (stage/'report.html').write_text(render(result,title),encoding='utf-8')
        (stage/'receipt.json').write_text(json.dumps({'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()},'scope':'文件摘要不是来源认证或审计意见'},ensure_ascii=False,indent=2),encoding='utf-8')
        os.rename(stage,out)
    finally:
        if stage.exists():
            if not stage.resolve().is_relative_to(out.parent.resolve()):raise ValueError('临时目录越界')
            shutil.rmtree(stage)
    return out

def cli(handlers,title):
    for s in (sys.stdout,sys.stderr):
        if hasattr(s,'reconfigure'):s.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=title);p.add_argument('command',choices=list(handlers));p.add_argument('--input',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
    try:
        if a.out_dir.exists():raise ValueError('输出已存在，旧结果保留')
        print('进度 1/3：读取并检查输入',file=sys.stderr)
        spec=read(a.input)
        print('进度 2/3：按声明资料计算与核对',file=sys.stderr)
        result=handlers[a.command](spec)
        print('进度 3/3：保存新报告与文件摘要',file=sys.stderr)
        out=publish(spec,result,a.out_dir,title)
        print('报告已生成：'+str(out/'report.html'));print('下一步：复查口径、来源和缺口，不能把程序通过当成原文已验证。');return 0
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as e:print('未完成：'+str(e)+'。请补齐资料并使用新目录。',file=sys.stderr);return 2
