import copy, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from marketlens.evidence_compare import compare
from marketlens.evidence_details import context
from marketlens.source_fetch import fetch
from unittest.mock import patch

class FrozenRegression(unittest.TestCase):
    def setUp(self):
        self.old={'methodVersion':'source-review/2','sources':[{'id':'a','actualSha256':'original'}],'claims':[{'id':'c','text':'回购是否兑现','aspectChecks':[{'sourceId':'a'}]}]}
    def test_no_mutation(self):
        frozen=copy.deepcopy(self.old); compare(self.old,self.old);self.assertEqual(frozen,self.old)
    def test_removed_claim_preserved(self):
        new=copy.deepcopy(self.old);new['claims']=[];self.assertEqual(compare(self.old,new)['removedClaims'][0]['id'],'c')
    def test_removed_source_requires_valid_references(self):
        new=copy.deepcopy(self.old);new['sources']=[]
        with self.assertRaises(ValueError):compare(self.old,new)
    def test_missing_reference(self):
        self.old['claims'][0]['aspectChecks'][0]['sourceId']='不存在'
        with self.assertRaises(ValueError):compare(self.old,self.old)
    def test_null_list(self):
        self.old['claims'][0]['links']=None
        with self.assertRaises(ValueError):compare(self.old,self.old)
    def test_unhashable_reference(self):
        self.old['claims'][0]['checks']=[{'sourceId':[]}]
        with self.assertRaises(ValueError):compare(self.old,self.old)
    def test_cross_page_quote_does_not_match(self):
        self.assertEqual(context(['公司已','完成回购'],'公司已完成回购'),[])
    def test_repeated_quote_retains_both_contexts(self):
        self.assertEqual(len(context(['已回购。但另一主体未回购。已回购。'],'已回购')),2)
    def test_wrong_page_does_not_match(self):
        self.assertEqual(context(['已回购','未回购'],'已回购',2),[])

for field in ('expectedSha256','hashMatch','page','locatorVerified','sourceUrl','publishedAt','title','sourceVersion','subjectId','sourceType','registeredAttachments','extractionCoverage'):
    def test(self,field=field):
        new=copy.deepcopy(self.old);new['sources'][0][field]='changed'
        result=compare(self.old,new)
        self.assertIn(field,result['sourceChanges'][0]['fields']);self.assertEqual(result['affectedClaims'][0]['id'],'c')
    setattr(FrozenRegression,'test_change_'+field,test)
for field in ('announcementMetrics','sourceRelations','searchLog','researchPlan'):
    def test(self,field=field):
        new=copy.deepcopy(self.old);new[field]=[{'changed':True}]
        self.assertIn(field,compare(self.old,new)['contextChanges'])
    setattr(FrozenRegression,'test_context_'+field,test)
for kind in ('sources','claims'):
    for value in ('duplicate','blank'):
        def test(self,kind=kind,value=value):
            if value=='duplicate':self.old[kind].append(copy.deepcopy(self.old[kind][0]))
            else:self.old[kind][0]['id']=' '
            with self.assertRaises(ValueError):compare(self.old,self.old)
        setattr(FrozenRegression,'test_'+kind+'_'+value,test)
class NetworkBoundary(unittest.TestCase):
    pass
for label,url in [('http','http://example.com'),('credentials','https://user:password@example.com'),('port','https://example.com:8443'),('loopback','https://127.0.0.1'),('private','https://10.0.0.1'),('metadata','https://169.254.169.254')]:
    def test(self,url=url):
        with patch('marketlens.source_fetch.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('marketlens.source_fetch.socket.socket') as connection:
            with self.assertRaises(ValueError):fetch(url)
            connection.assert_not_called()
    setattr(NetworkBoundary,'test_'+label,test)


class ChineseStageScenarios(unittest.TestCase):
    def run_stage(self,action,marker):
        import tempfile,hashlib
        from marketlens.source_review import review
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); quote='公司'+marker+action+'相关事项，具体进展以之后公告为准。'
            file=base/'公告.md';file.write_text(quote,encoding='utf-8')
            spec={'inputSchema':'source-review/2','sources':[{'id':'a','file':'公告.md','publishedAt':'2026-01-01','expectedSha256':hashlib.sha256(file.read_bytes()).hexdigest()}],'claims':[{'id':'c','text':'公司已'+action,'checks':[{'aspect':'stage','expected':'已'+action,'sourceId':'a','excerpt':quote,'finding':'supports','rationale':'待核声明','reviewer':'测试声明者','reviewedAt':'2026-02-01T10:00:00+08:00'}]}]}
            row=review(spec,base)['claims'][0]['aspectChecks'][0]
            self.assertEqual(row['finding'],'supports');self.assertEqual(row['effectiveFinding'],'unknown');self.assertTrue(row['riskQuestions'])
for action in ('交付','实施','完成','签约'):
    for marker in ('未','尚未','拟','计划','预计','有望','可能','或将'):
        def test(self,action=action,marker=marker):self.run_stage(action,marker)
        setattr(ChineseStageScenarios,'test_'+action+'_'+marker,test)

if __name__=='__main__':unittest.main()

