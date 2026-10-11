# SPDX-License-Identifier: MIT
"""Signed disclosure metrics are distinct from transaction cumulative cash."""
from datetime import date
from decimal import Decimal, InvalidOperation

UNITS={'元':Decimal(1),'万元':Decimal(10000),'亿元':Decimal(100000000)}
def number(value):
    if isinstance(value,bool): raise ValueError('数值不能为布尔值')
    try: result=Decimal(str(value))
    except InvalidOperation: raise ValueError('财务指标须为有限数字，未知留空')
    if not result.is_finite(): raise ValueError('财务指标须为有限数字')
    return result

def review(items,source_ids):
    if not isinstance(items,list) or len(items)>100: raise ValueError('公告指标最多100项')
    rows=[];previous={};ids=set()
    for item in items:
        required={'id','sourceId','subject','metric','periodStart','periodEnd','publishedAt','basis','auditStatus','unit','currency','disclosureType','value','lower','upper','corrects'}
        if not isinstance(item,dict) or set(item)!=required: raise ValueError('公告指标字段不完整或含未知字段；请按模板填写')
        if item['id'] in ids or not isinstance(item['id'],str) or not item['id'].strip(): raise ValueError('公告指标ID须唯一')
        ids.add(item['id'])
        if item['sourceId'] not in source_ids: raise ValueError('公告指标须关联已登记原文件')
        for field in ('subject','metric','basis','currency'):
            if not isinstance(item[field],str) or not item[field].strip(): raise ValueError('指标、主体、币种和报表口径须明确；无法确定时不做比较')
        if item['unit'] not in UNITS: raise ValueError('支持元、万元、亿元；其他单位不自动换算')
        if item['auditStatus'] not in ('未知','未经审计','已审计','已预审'): raise ValueError('审计状态无效')
        if item['disclosureType'] not in ('预告','快报','年报','更正','重述','补充'): raise ValueError('公告类型无效')
        try:
            start=date.fromisoformat(item['periodStart']);end=date.fromisoformat(item['periodEnd']);published=date.fromisoformat(item['publishedAt'])
        except (ValueError,TypeError): raise ValueError('公告日期与报告期须为YYYY-MM-DD')
        if start>end: raise ValueError('报告期开始不能晚于结束')
        if item['disclosureType']!='预告' and end>published: raise ValueError('实际财务报告期不能晚于发布日期；预计数据请使用预告')
        factor=UNITS[item['unit']]
        values={k:None if item[k] is None else number(item[k])*factor for k in ('value','lower','upper')}
        if (values['lower'] is None)!=(values['upper'] is None): raise ValueError('区间上下限需同时提供或同时未知')
        if values['lower'] is not None and values['lower']>values['upper']: raise ValueError('带符号区间下限不能大于上限，例如亏损5000万至4000万填写-5000、-4000')
        key=tuple(item[k] for k in ('subject','metric','periodStart','periodEnd','basis','currency'))
        history=previous.setdefault(key,[])
        if history and item['publishedAt']<history[-1]['publishedAt']: raise ValueError('同口径指标版本须按披露日排序')
        if item['corrects'] is not None and (not history or item['corrects']!=history[-1]['id']): raise ValueError('更正须关联同指标同口径紧前版本')
        row=dict(item,normalized={k:None if v is None else str(v) for k,v in values.items()},comparisonScope='仅按声明字段比较，不认证审计状态或违规',warnings=[])
        forecast=next((x for x in reversed(history) if x['disclosureType']=='预告' and x['normalized']['lower'] is not None),None)
        if values['value'] is not None and forecast and item['disclosureType']!='预告':
            low=Decimal(forecast['normalized']['lower']);high=Decimal(forecast['normalized']['upper']);actual=values['value']
            outside=actual<low or actual>high;row['forecastComparison']=dict(forecastId=forecast['id'],outside=outside,differenceToNearestBound=str(actual-low if actual<low else actual-high if actual>high else Decimal(0)),ratio=None,reason='带符号区间比较；不以跨零或负数区间生成误导比例，不判定违规')
            if outside: row['warnings'].append('实际值超出已登记预告区间，请核对更正、期间、审计和报表口径')
        if history and values['value'] is not None and history[-1]['normalized']['value'] is not None:
            old=Decimal(history[-1]['normalized']['value']);row['versionDifference']=str(values['value']-old)
            row['differenceMeaning']='同报告期版本差额，不是本期业务增量'
            if old!=0 and abs(values['value']/old)>=1000: row['warnings'].append('版本量级变化较大，请核对原始单位；不自动判错')
        history.append(row);rows.append(row)
    return rows
