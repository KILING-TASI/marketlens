# SPDX-License-Identifier: MIT
"""Traceable context and review records; declarations are not authentication."""
import hashlib
import re
from datetime import date,datetime,timezone,timedelta
from urllib.parse import urlsplit
from .review_io import instant

ASPECTS={'subject':'主体','action':'动作','amount':'金额','period':'期间','stage':'阶段','scope':'范围','identity':'身份','time':'时间'}
CN_TIME=timezone(timedelta(hours=8))

def text(value,label,limit=20000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit: raise ValueError(label+'须为非空文字，长度不超过'+str(limit))
    return value

def scan(content):
    patterns=[('uncertain',r'据传|传闻|或将|拟|有望|疑似|有消息称','区分传闻存在、计划发布与实际执行'),
              ('actor-boundary',r'国家队|主力|(?<!监管)(?<!政府)机构|游资|庄家|北向|央企|国资|外资|险资|社保|量化|私募|大资金','核对主体、统计边界和识别依据；不推断动机'),
              ('absolute-or-trade',r'必然|一定|百分之百|满仓|翻倍|必涨|肯定大涨|稳赚不赔|确定性机会|拉升在即','核对引用、否定或收益保证语境，不背书交易建议'),
              ('stage-check',r'尚未|未实施|拟|否认|澄清|更正|终止|未经审计|不予置评|未披露','区分未实施、未披露、不予置评、否认及更正范围')]
    result=[]
    for code,pattern,question in patterns:
        for match in re.finditer(pattern,content):
            result.append(dict(code=code,matched=match.group(),offset=match.start(),context=content[max(0,match.start()-60):match.end()+100],question=question,scope='措辞核对线索，可能误报或漏报，不自动判真伪'))
            if len(result)>=100: return result
    return sorted(result,key=lambda r:r['offset'])

def context(pages,excerpt,page=None):
    if not isinstance(excerpt,str) or not excerpt.strip(): return []
    matches=[]
    for n,content in enumerate(pages,1):
        if page is not None and page!=n:continue
        start=0
        while len(matches)<20:
            offset=content.find(excerpt,start)
            if offset<0:break
            matches.append(dict(page=n,offset=offset,before=content[max(0,offset-250):offset],excerpt=excerpt,after=content[offset+len(excerpt):offset+len(excerpt)+250],scope='提取文本上下文；不保证表格布局、附件或完整语义'))
            start=offset+len(excerpt)
    return matches

def enrich_source(row,pages,base,verify_urls=False,cutoff=None):
    row['contexts']=context(pages,row.get('excerpt'),row.get('page'))
    row['fullTextAlerts']=[]
    for n,content in enumerate(pages,1):
        row['fullTextAlerts'].extend(dict(w,page=n) for w in scan(content))
    row['fullTextAlerts']=row['fullTextAlerts'][:100]
    row['alertScope']='读取的全文，最多展示100项；非完整语义审查'
    normalized=re.sub(r'\s+',' ','\n'.join(pages)).strip()
    row['normalizedTextSha256']=hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else None
    row['extractionCoverage']=dict(pages=len(pages),emptyPages=[n for n,p in enumerate(pages,1) if not p.strip()],attachmentsChecked=False,tableLayoutVerified=False,scope='附件需单独登记；PDF提取顺序和表格脚注需人工复核')
    address=row.get('sourceUrl')
    row['urlCheck']=dict(status='not-visited',requested=verify_urls,address=address,bytesMatch=None,reason='本次未访问此地址；不能证明文件来自该页面')
    if address is not None:
        try: parsed=urlsplit(address)
        except (ValueError,TypeError):parsed=None
        if not parsed or parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            row['urlCheck'].update(status='invalid-address',reason='来源地址不是无账号信息的HTTPS地址；保留声明，不访问')
        elif verify_urls:
            from .source_fetch import fetch
            try:
                body,receipt=fetch(address);digest=hashlib.sha256(body).hexdigest()
                row['urlCheck'].update(status='visited',bytesMatch=digest==row['actualSha256'],downloadSha256=digest,receipt=receipt,checkedAt=datetime.now(timezone.utc).isoformat(),reason='实际下载字节与本地文件比较；不同可能由版本、动态内容或错误文件造成，不自动判伪造')
            except (OSError,ValueError) as error:row['urlCheck'].update(status='unavailable',reason=str(error))
    published=row.get('publishedAt')
    try:
        if published is None:row['timeCheck']=dict(precision='unknown',intradayKnown=False,reason='首次披露时间未知；取得日期不替代发布时间',availableAtCutoff=None)
        elif isinstance(published,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',published):
            day=date.fromisoformat(published)
            row['timeCheck']=dict(precision='day',intradayKnown=False,reason='只有日期，按中国市场日期比较，不能确定盘中是否已知；网页更新日期未证明首次披露',availableAtCutoff=None if cutoff is None or day==cutoff.astimezone(CN_TIME).date() else day<cutoff.astimezone(CN_TIME).date())
        else:
            timestamp=instant(published);row['timeCheck']=dict(precision='instant',intradayKnown=False,reason='带时区时间由输入者声明，尚未认证首次披露时刻',availableAtCutoff=None if cutoff is None else timestamp<=cutoff)
    except (ValueError,TypeError):row['timeCheck']=dict(precision='invalid',intradayKnown=False,availableAtCutoff=None,reason='披露时间格式无效，不据此确认当时可知')
    row['timeCheck']['cutoffRequested']=cutoff is not None
    row['timeCheck']['cutoff']=cutoff.isoformat() if cutoff else None
    now=datetime.now(timezone.utc)
    row['timeCheck']['observedAt']=now.isoformat()
    row['timeCheck']['futurePublication']=False
    if row['timeCheck']['precision']=='instant':row['timeCheck']['futurePublication']=instant(published)>now
    elif row['timeCheck']['precision']=='day':row['timeCheck']['futurePublication']=date.fromisoformat(published)>now.astimezone(CN_TIME).date()

def links_and_search(spec,rows):
    ids={r['id'] for r in rows};relations=spec.get('sourceRelations',[])
    if not isinstance(relations,list) or len(relations)>200:raise ValueError('来源关系最多200项')
    for relation in relations:
        if not isinstance(relation,dict) or set(relation)!={'from','to','type','reason'}:raise ValueError('来源关系须明确from、to、type、reason')
        if not isinstance(relation['from'],str) or not isinstance(relation['to'],str) or relation['from'] not in ids or relation['to'] not in ids or relation['from']==relation['to']:raise ValueError('来源关系引用无效')
        if relation['type'] not in ('reprint','progress','correction','denial','attachment','independent-check'):raise ValueError('来源关系类型无效')
        text(relation['reason'],'关系理由')
    searches=spec.get('searchLog',[])
    if not isinstance(searches,list) or len(searches)>100:raise ValueError('查找记录最多100项')
    for log in searches:
        if not isinstance(log,dict) or set(log)!={'query','scope','status','checkedAt','sourceIds','reason'}:raise ValueError('查找记录字段不完整')
        text(log['query'],'查找问题');text(log['scope'],'查找范围');text(log['reason'],'查找结果说明')
        if log['status'] not in ('not-searched','searched-no-find','found','unavailable'):raise ValueError('查找状态无效')
        if not isinstance(log['sourceIds'],list) or any(not isinstance(x,str) or x not in ids for x in log['sourceIds']):raise ValueError('查找结果引用资料不存在')
        if log['status']!='not-searched':
            checked=instant(log['checkedAt'])
            if checked>datetime.now(timezone.utc):raise ValueError('查找完成时间在未来，不能声明已完成')
            if log['status']=='found':
                for sid in log['sourceIds']:
                    row=next(r for r in rows if r['id']==sid);published=row.get('publishedAt')
                    if row.get('timeCheck',{}).get('precision')=='instant' and checked<instant(published):raise ValueError('查找时间早于所引用资料的声明披露时刻')
                    if row.get('timeCheck',{}).get('precision')=='day' and checked.astimezone(CN_TIME).date()<date.fromisoformat(published):raise ValueError('查找日期早于所引用资料的声明披露日期')
        elif log['checkedAt'] is not None:raise ValueError('未查找不能填写已查时间')
        if log['status']=='found' and not log['sourceIds']:raise ValueError('找到资料须提供来源引用')
    return relations,searches

def aspects(claim,rows,pages):
    checks=claim.get('checks',[]);result=[];ids={r['id'] for r in rows}
    if not isinstance(checks,list) or len(checks)>50:raise ValueError('主张逐项核对最多50项')
    for check in checks:
        required={'aspect','expected','sourceId','excerpt','finding','rationale','reviewer','reviewedAt'}
        if not isinstance(check,dict) or set(check)!=required:raise ValueError('逐项核对须按模板填写字段')
        if not isinstance(check['aspect'],str) or check['aspect'] not in ASPECTS or check['finding'] not in ('supports','contradicts','partial','unknown'):raise ValueError('逐项核对类别或意见无效')
        text(check['expected'],'预期核对内容');text(check['rationale'],'核对依据')
        if check['sourceId'] is not None and (not isinstance(check['sourceId'],str) or check['sourceId'] not in ids):raise ValueError('核对引用资料不存在')
        if check['finding']!='unknown':
            text(check['reviewer'],'复核声明者');instant(check['reviewedAt']);text(check['excerpt'],'核对原句')
            if check['sourceId'] is None:raise ValueError('有判断须引用资料')
        source=next((r for r in rows if r['id']==check['sourceId']),None)
        locations=context(pages.get(check['sourceId'],[]),check['excerpt'],source.get('page') if source else None)
        matched=bool(locations)
        usable=matched and source is not None and source.get('locatorVerified') is not False and source.get('hashMatch') is not False and source.get('urlCheck',{}).get('bytesMatch') is not False
        if source and source.get('urlCheck',{}).get('requested') and source['urlCheck'].get('bytesMatch') is not True:usable=False
        if source and source.get('timeCheck',{}).get('cutoffRequested') and source['timeCheck']['availableAtCutoff'] is not True:usable=False
        if source and source.get('timeCheck',{}).get('cutoff') and check['reviewedAt'] is not None and instant(check['reviewedAt'])>instant(source['timeCheck']['cutoff']):usable=False
        risks=[]
        if check['reviewedAt'] is not None:
            reviewed=instant(check['reviewedAt'])
            if reviewed>datetime.now(timezone.utc):risks.append('复核时间在未来，不能称已完成')
            if source and source.get('timeCheck',{}).get('precision')=='instant' and reviewed<instant(source['publishedAt']):risks.append('复核早于声明披露时刻')
            if source and source.get('timeCheck',{}).get('precision')=='day' and reviewed.astimezone(CN_TIME).date()<date.fromisoformat(source['publishedAt']):risks.append('复核日期早于声明披露日期')
        if source and (source.get('timeCheck',{}).get('futurePublication') or source.get('timeCheck',{}).get('precision')=='invalid'):risks.append('声明披露时间在未来或格式无效，时点需核')
        if check['finding']=='supports':
            expected=check['expected'].replace('已经','已');quote=check['excerpt'] or ''
            for action in ('交付','实施','完成','签约'):
                if '已'+action in expected and ('未'+action in quote or '尚未'+action in quote):risks.append('声明支持与原句未'+action+'措辞疑似矛盾')
            if any(w in expected for w in ('全部','所有')) and '否认' in quote and any(w in quote for w in ('其他','部分','仅')):risks.append('局部否认不能直接推广为全部对象')
            if check['aspect'] in ('identity','subject') and check['expected'] not in quote:risks.append('身份名称未在所引原句直接对应；别名或母子公司关系需另附依据')
        if risks:usable=False
        result.append(dict(check,excerptMatched=matched,matchedContexts=locations,riskQuestions=risks,effectiveFinding=check['finding'] if usable else 'unknown',reason='仅记录复核声明，不认证语义或复核身份' if usable else '原句、定位、摘要、时点或限定模式存在缺口：'+'；'.join(risks or ['来源对应或截止条件未核明'])+'；意见保留为待核建议',semanticVerification='declared-only'))
    return result
