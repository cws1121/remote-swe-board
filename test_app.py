import json,os,pathlib,tempfile,unittest
os.environ['REMOTE_SWE_DATA_DIR']=tempfile.mkdtemp(prefix='remote-swe-test-')
import app,board
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):app.init()
 def job(self,url='https://example.com/job',posted='2026-10-04T13:00:00Z'):
  return board.row('Senior Software Engineer','Example Inc','Worldwide','Angular and .NET','Test',url,posted,world=True)
 def test_comments_survive_refresh(self):
  row=self.job();app.save_rows([row])
  with app.connect() as c:c.execute('UPDATE jobs SET status=?,comments=? WHERE id=?',('Applied','Ask about contractor terms',row['Job ID']))
  row['Salary']='USD 100000';app.save_rows([row])
  j=next(j for j in app.get_jobs() if j['Job ID']==row['Job ID']);self.assertEqual(j['Status'],'Applied');self.assertEqual(j['Comments'],'Ask about contractor terms');self.assertEqual(j['Salary'],'USD 100000')
 def test_same_day_timestamp_order(self):
  a=self.job('https://example.com/a','2026-10-04T11:00:00Z');a['Company']='A';b=self.job('https://example.com/b','2026-10-04T15:00:00Z');b['Company']='B';app.save_rows([a,b]);ids=[j['Job ID'] for j in app.get_jobs()];self.assertLess(ids.index(b['Job ID']),ids.index(a['Job ID']))
 def test_legal_us_requirement(self):
  text='Applicants must be able to work legally within the United States. Please, no 3rd party inquiries.'
  self.assertEqual(board.eligible('Worldwide',text,True)[0],'Excluded')
 def test_source_label_is_not_override(self):self.assertEqual(board.eligible('Worldwide','USA only',True)[0],'Excluded')
 def test_rss_publication_date(self):self.assertEqual(board.date('Sat, 03 Oct 2026 16:00:00 +0000'),'2026-10-03')
 def test_missing_date_stays_unknown(self):self.assertEqual(self.job(posted='')['Published at'],'')
if __name__=='__main__':unittest.main()

class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import threading
  app.init();cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);cls.port=cls.server.server_port
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def call(self,path,body=None,token=True):
  import urllib.request
  headers={'Content-Type':'application/json'}
  if token:headers['X-Board-Token']=app.TOKEN
  req=urllib.request.Request('http://127.0.0.1:'+str(self.port)+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
  with urllib.request.urlopen(req) as r:return json.load(r)
 def test_save_and_backup_restore(self):
  row=board.row('Senior Developer','API Test','Worldwide','Angular','Test','https://api-test.com/job',world=True);app.save_rows([row])
  self.call('/api/screen',{'id':row['Job ID'],'status':'Saved','comments':'Check pay and timezone'})
  backup=self.call('/api/backup');self.call('/api/screen',{'id':row['Job ID'],'status':'Rejected','comments':'changed'})
  self.call('/api/restore',backup)
  j=next(r for r in self.call('/api/jobs')['jobs'] if r['Job ID']==row['Job ID']);self.assertEqual(j['Status'],'Saved');self.assertEqual(j['Comments'],'Check pay and timezone')
 def test_rejects_unauthenticated_write(self):
  import urllib.error
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/api/screen',{'id':'x','status':'New'},False)
  self.assertEqual(e.exception.code,403)
 def test_rejects_invalid_status(self):
  import urllib.error
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/api/screen',{'id':'x','status':'Unexpected'})
  self.assertEqual(e.exception.code,400)
