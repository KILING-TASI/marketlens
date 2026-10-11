# SPDX-License-Identifier: MIT
"""Original synthetic Chinese cases and controlled HTTPS/PDF integration."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from marketlens.source_review import review, artifact
from marketlens.evidence_compare import compare
from marketlens.source_fetch import fetch, FetchError

class EvidenceExpansion(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.quote='教学公司已完成回购。'
        self.file=self.base/'公告.md';self.file.write_text(self.quote,encoding='utf-8')
        self.spec=dict(inputSchema='source-review/2',sources=[dict(id='a',file='公告.md',publishedAt='2026-01-01')],claims=[dict(id='c',text='教学公司已完成回购',checks=[dict(aspect='stage',expected='已完成',sourceId='a',excerpt=self.quote,finding='supports',rationale='教学声明',reviewer='测试声明者',reviewedAt='2026-02-01T10:00:00+08:00')])])
    def tearDown(self):self.tmp.cleanup()
    def result(self):return review(self.spec,self.base)
    def metric(self):
        return dict(id='m',sourceId='a',subject='教学公司',metric='净利润',periodStart='2025-01-01',periodEnd='2025-12-31',publishedAt='2026-01-01',basis='合并',auditStatus='未经审计',unit='万元',currency='CNY',disclosureType='快报',value=100,lower=None,upper=None,corrects=None,evidenceExcerpt='净利润100万元')
    def binding(self):
        self.spec['announcementMetrics']=[self.metric()]
        self.spec['metricBindings']=[dict(claimId='c',metricId='m',rationale='教学关联，待核真实含义')]
    def test_unambiguous_positive_not_globally_blocked(self):
        self.assertEqual(self.result()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'supports')
    def test_surrounding_negative_downgrades_cut_quote(self):
        self.file.write_text('媒体称教学公司已完成回购。本公司表示上述消息不属实。',encoding='utf-8')
        self.assertEqual(self.result()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_condition_in_next_sentence(self):
        self.file.write_text(self.quote+'该事项仍需履行审批，前句为媒体转述。',encoding='utf-8')
        self.assertEqual(self.result()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_pronoun_requires_mapping(self):
        q='其已完成回购。';self.file.write_text('甲公司介绍乙公司。'+q,encoding='utf-8');self.spec['claims'][0]['checks'][0]['excerpt']=q
        self.assertEqual(self.result()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_counter_opinion_retained(self):
        self.file.write_text('尚未完成回购。',encoding='utf-8');c=self.spec['claims'][0]['checks'][0];c.update(excerpt='尚未完成回购。',finding='contradicts')
        self.assertEqual(self.result()['claims'][0]['aspectChecks'][0]['effectiveFinding'],'contradicts')
    def test_missing_required_attachment_blocks_support(self):
        self.spec['sources'][0]['requiredAttachments']=['attachment']
        r=self.result();self.assertEqual(r['sources'][0]['attachmentCoverage']['missing'],['attachment']);self.assertEqual(r['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_read_attachment_without_relation_is_missing(self):
        self.spec['sources'][0]['requiredAttachments']=['b'];self.spec['sources'].append(dict(id='b',file='公告.md'))
        self.assertEqual(self.result()['sources'][0]['attachmentCoverage']['missing'],['b'])
    def attach(self):
        self.spec['sources'][0]['requiredAttachments']=['b'];self.spec['sources'].append(dict(id='b',file='公告.md'))
        self.spec['sourceRelations']=[dict(**{'from':'b','to':'a','type':'attachment','reason':'教学声明附件'})]
    def test_attachment_read_not_layout_certified(self):
        self.attach();r=self.result();self.assertEqual(r['sources'][0]['attachmentCoverage']['available'],['b']);self.assertFalse(r['sources'][1]['extractionCoverage']['tableLayoutVerified'])
    def test_bad_attachment_hash_remains_missing(self):
        self.attach();self.spec['sources'][1]['expectedSha256']='0'*64
        self.assertEqual(self.result()['sources'][0]['attachmentCoverage']['missing'],['b'])
    def test_unreadable_attachment_remains_missing(self):
        self.attach();self.spec['sources'][1]['file']='不存在.pdf'
        self.assertEqual(self.result()['sources'][0]['attachmentCoverage']['missing'],['b'])
    def test_empty_attachment_not_usable(self):
        self.attach();(self.base/'empty.txt').write_text('',encoding='utf-8');self.spec['sources'][1]['file']='empty.txt'
        self.assertEqual(self.result()['sources'][0]['attachmentCoverage']['missing'],['b'])
    def test_attachment_revision_affects_parent_claim(self):
        self.attach();(self.base/'attachment.txt').write_text('初版附件',encoding='utf-8');self.spec['sources'][1]['file']='attachment.txt'
        old=self.result();(self.base/'attachment.txt').write_text('更正附件',encoding='utf-8');new=self.result()
        self.assertEqual(compare(old,new)['affectedClaims'][0]['sources'],['b'])
    def test_metric_hash_failure_not_hidden_by_quote_match(self):
        self.binding();self.file.write_text('净利润100万元',encoding='utf-8');self.spec['sources'][0]['expectedSha256']='0'*64
        check=self.result()['announcementMetrics'][0]['sourceEvidenceCheck'];self.assertTrue(check['excerptMatched']);self.assertFalse(check['sourceChecksPassed'])
    def test_url_rate_limit_preserved_in_review(self):
        self.spec['sources'][0]['sourceUrl']='https://example.com/original'
        with patch('marketlens.source_fetch.fetch',side_effect=FetchError('限流','rate-limited',429,'60')):
            r=review(self.spec,self.base,True)
        self.assertEqual(r['sources'][0]['urlCheck']['failure']['status'],429);self.assertEqual(r['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_changed_page_cannot_upgrade_opinion(self):
        self.spec['sources'][0]['sourceUrl']='https://example.com/original'
        with patch('marketlens.source_fetch.fetch',return_value=(b'updated page',{'finalUrl':'https://example.com/original'})):
            r=review(self.spec,self.base,True)
        self.assertFalse(r['sources'][0]['urlCheck']['bytesMatch']);self.assertEqual(r['claims'][0]['aspectChecks'][0]['effectiveFinding'],'unknown')
    def test_timeout_preserved_as_unavailable(self):
        self.spec['sources'][0]['sourceUrl']='https://example.com/original'
        with patch('marketlens.source_fetch.fetch',side_effect=TimeoutError('controlled timeout')):
            r=review(self.spec,self.base,True)
        self.assertEqual(r['sources'][0]['urlCheck']['status'],'unavailable');self.assertFalse(r['sources'][0]['urlCheck']['failure']['retried'])
    def test_removed_bound_metric_affects_claim(self):
        self.binding();old=self.result();self.spec['announcementMetrics']=[];self.spec['metricBindings']=[];new=self.result()
        d=compare(old,new);self.assertEqual(d['metricChanges'],['m']);self.assertEqual(d['affectedClaims'][0]['metrics'],['m'])
    def test_metric_value_changes_bound_claim_only(self):
        self.binding();self.spec['claims'].append(dict(id='other',text='未关联问题'));old=self.result();self.spec['announcementMetrics'][0]['value']=200;new=self.result()
        self.assertEqual([c['id'] for c in compare(old,new)['affectedClaims']],['c'])
    def test_bound_metric_source_changed_without_claim_links(self):
        self.binding();self.spec['claims'][0].pop('checks');old=self.result();self.file.write_text('教学公告改版。',encoding='utf-8');new=self.result()
        self.assertEqual(compare(old,new)['affectedClaims'][0]['sources'],['a'])
    def test_binding_removed_is_visible_without_numeric_change(self):
        self.binding();old=self.result();self.spec['metricBindings']=[]
        self.assertEqual(compare(old,self.result())['affectedClaims'][0]['id'],'c')
    def test_no_invented_binding(self):
        self.binding();self.spec['metricBindings']=[];old=self.result();self.spec['announcementMetrics'][0]['value']=200
        self.assertEqual(compare(old,self.result())['affectedClaims'],[])
    def test_bindings_duplicate_rejected(self):
        self.binding();self.spec['metricBindings']*=2
        with self.assertRaises(ValueError):self.result()
    def test_binding_unknown_claim_rejected(self):
        self.binding();self.spec['metricBindings'][0]['claimId']='missing'
        with self.assertRaises(ValueError):self.result()
    def test_binding_unknown_metric_rejected(self):
        self.binding();self.spec['metricBindings'][0]['metricId']='missing'
        with self.assertRaises(ValueError):self.result()
    def test_binding_false_certification_rejected(self):
        self.binding();self.spec['metricBindings'][0]['verified']=True
        with self.assertRaises(ValueError):self.result()
    def test_metric_wrong_page_does_not_match(self):
        self.binding();self.file.write_text('净利润100万元',encoding='utf-8');self.spec['announcementMetrics'][0]['evidencePage']=2
        self.assertFalse(self.result()['announcementMetrics'][0]['sourceEvidenceCheck']['excerptMatched'])
    def test_metric_location_includes_footnote(self):
        self.binding();self.file.write_text('表头：单位万元。净利润100万元。脚注：未经审计。',encoding='utf-8')
        hit=self.result()['announcementMetrics'][0]['sourceEvidenceCheck']['matchedContexts'][0]
        self.assertIn('单位',hit['before']);self.assertIn('未经审计',hit['after'])
    def test_metric_bool_page_rejected(self):
        self.binding();self.spec['announcementMetrics'][0]['evidencePage']=True
        with self.assertRaises(ValueError):self.result()
    def test_invalid_attachment_list_rejected(self):
        self.spec['sources'][0]['requiredAttachments']=[[]]
        with self.assertRaises(ValueError):self.result()
    def test_same_source_attachment_rejected(self):
        self.spec['sources'][0]['requiredAttachments']=['a']
        with self.assertRaises(ValueError):self.result()

class ControlledHTTPS(unittest.TestCase):
    def response(self,status=200,body=b'original',headers=None):
        r=Mock();r.status=status;r.getheader.side_effect=lambda key,default=None:(headers or {}).get(key,default);r.read.return_value=body;return r
    def fetch_responses(self,responses,addresses=None):
        connections=[]
        for response in responses:
            c=Mock();c.getresponse.return_value=response;connections.append(c)
        self.connections=connections
        with patch('marketlens.source_fetch.socket.getaddrinfo',side_effect=addresses or (lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])),patch('marketlens.source_fetch.socket.socket'),patch('marketlens.source_fetch.ssl.create_default_context'),patch('marketlens.source_fetch.http.client.HTTPSConnection',side_effect=connections):
            return fetch('https://example.com/original')
    def test_429_has_failure_receipt_and_no_retry(self):
        with self.assertRaises(FetchError) as error:self.fetch_responses([self.response(429,headers={'Retry-After':'60'})])
        self.assertEqual(error.exception.details['code'],'rate-limited');self.assertEqual(error.exception.details['retryAfter'],'60');self.assertFalse(error.exception.details['retried']);self.connections[0].close.assert_called_once()
    def test_503_retry_header_is_declaration(self):
        with self.assertRaises(FetchError) as error:self.fetch_responses([self.response(503,headers={'Retry-After':'Wed, 01 Jan 2099 00:00:00 GMT'})])
        self.assertEqual(error.exception.details['status'],503);self.assertFalse(error.exception.details['retried'])
    def test_redirect_chain_retained(self):
        body,receipt=self.fetch_responses([self.response(302,headers={'Location':'/changed'}),self.response()])
        self.assertEqual(body,b'original');self.assertEqual(len(receipt['redirectChain']),2);self.assertEqual(receipt['finalUrl'],'https://example.com/changed')
    def test_redirect_private_address_rejected(self):
        with self.assertRaises(ValueError):self.fetch_responses([self.response(302,headers={'Location':'https://private.invalid'})],addresses=[[(2,1,6,'',('8.8.8.8',443))],[(2,1,6,'',('127.0.0.1',443))]])
    def test_redirect_http_rejected(self):
        with self.assertRaises(ValueError):self.fetch_responses([self.response(302,headers={'Location':'http://example.com'})])
    def test_redirect_limit(self):
        with self.assertRaises(ValueError):self.fetch_responses([self.response(302,headers={'Location':'/again'}) for _ in range(4)])
    def test_redirect_without_location(self):
        with self.assertRaises(ValueError):self.fetch_responses([self.response(302)])
    def test_compressed_response_rejected(self):
        with self.assertRaises(ValueError):self.fetch_responses([self.response(headers={'Content-Encoding':'gzip'})])
    def test_oversize_response_rejected(self):
        with self.assertRaises(ValueError):self.fetch_responses([self.response(body=b'x'*(16*1024*1024+1))])
    def test_404_preserved(self):
        with self.assertRaises(FetchError) as error:self.fetch_responses([self.response(404)])
        self.assertEqual(error.exception.details['code'],'http-error')

@unittest.skipUnless(importlib.util.find_spec('pypdf'),'optional PDF component not installed')
class RealPDF(unittest.TestCase):
    setUp=EvidenceExpansion.setUp
    tearDown=EvidenceExpansion.tearDown
    result=EvidenceExpansion.result
    def pdf(self,encrypted=False):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        writer=PdfWriter()
        for lines in (['Table header: amount CNY','Revenue 100','Footnote: unaudited'],['Correction: Revenue 80'],[]):
            page=writer.add_blank_page(width=300,height=300)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 20 270 Td '+' '.join(('('+line+') Tj 0 -20 Td') for line in lines)+' ET').encode('ascii'));page[NameObject('/Contents')]=writer._add_object(stream)
        if encrypted:writer.encrypt('password')
        path=self.base/'teaching.pdf';writer.write(path);return path
    def test_real_pdf_pages_footnotes_and_empty_page(self):
        path=self.pdf();sha,pages=artifact(path)
        self.assertEqual(sha,hashlib.sha256(path.read_bytes()).hexdigest());self.assertEqual(len(pages),3);self.assertIn('Footnote: unaudited',pages[0]);self.assertFalse(pages[2].strip())
    def test_real_pdf_page_and_quote(self):
        self.pdf();self.spec['sources'][0].update(file='teaching.pdf',page=2,excerpt='Revenue 80');self.spec['claims'][0].pop('checks')
        r=self.result()['sources'][0];self.assertTrue(r['excerptFound']);self.assertEqual(r['contexts'][0]['page'],2);self.assertEqual(r['extractionCoverage']['emptyPages'],[3]);self.assertFalse(r['extractionCoverage']['tableLayoutVerified'])
    def test_pdf_wrong_page_does_not_match(self):
        self.pdf();self.spec['sources'][0].update(file='teaching.pdf',page=1,excerpt='Revenue 80');self.spec['claims'][0].pop('checks')
        self.assertFalse(self.result()['sources'][0]['excerptFound'])
    def test_encrypted_pdf_not_read_as_complete(self):
        self.pdf(True);self.spec['sources'][0]['file']='teaching.pdf';self.spec['claims'][0].pop('checks')
        self.assertFalse(self.result()['sources'][0]['sourceRead'])

if __name__=='__main__':unittest.main()
