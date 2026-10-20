import unittest,tempfile,os,importlib.util,threading,json,urllib.request,urllib.error,http.cookiejar,time
from pathlib import Path
class Workflow(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();os.environ['FIT_DATA']=cls.tmp.name
  spec=importlib.util.spec_from_file_location('fit_server',Path(__file__).resolve().parents[1]/'server.py');cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)
  cls.server=cls.m.ThreadingHTTPServer(('127.0.0.1',0),cls.m.Handler);cls.url='http://127.0.0.1:'+str(cls.server.server_port);threading.Thread(target=cls.server.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.tmp.cleanup();os.environ.pop('FIT_DATA',None)
 def setUp(self):self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def call(self,path,data=None,client=None):
  req=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
  try:
   with (client or self.client).open(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_full_journey(self):
  self.assertIsNone(self.call('session')[1]['candidate']);self.assertEqual(self.call('hr')[0],401)
  self.assertEqual(self.call('start',{'name':'Иванов'})[0],400)
  c=self.call('start',{'name':'Тестовый Кандидат'})[1]['candidate'];token=c['id'];self.assertAlmostEqual(c['deadline']-c['start'],259200)
  self.assertEqual(self.call('start',{'name':'Другой Кандидат'})[1]['candidate']['id'],token)
  self.assertEqual(self.call('complete',{'block':2,'confirmed':True})[0],409)
  self.assertEqual(self.call('feedback',{'text':'Рано'})[0],409)
  self.assertEqual(self.call('complete',{'block':1})[0],400)
  first=self.call('complete',{'block':1,'confirmed':True})[1]['candidate'];self.assertEqual(first['progress'],33)
  self.assertEqual(self.call('complete',{'block':1,'confirmed':True})[1]['candidate']['b1'],first['b1'])
  self.assertEqual(self.call('complete',{'block':3,'confirmed':True})[0],409)
  self.assertEqual(self.call('complete',{'block':2,'confirmed':True})[1]['candidate']['progress'],67)
  self.assertEqual(self.call('complete',{'block':3,'confirmed':True})[1]['candidate']['progress'],100)
  self.assertEqual(self.call('feedback',{'text':'Всё понятно!'})[0],200)
  other=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  self.assertEqual(self.call('restore',{'code':token},other)[1]['candidate']['progress'],100)
  self.assertEqual(self.call('hr/login',{'password':'wrong'})[0],401)
  self.assertEqual(self.call('hr/login',{'password':self.m.PASSWORD})[0],200)
  found=next(r for r in self.call('hr')[1]['candidates'] if r['id']==token);self.assertEqual(found['feedback'],'Всё понятно!');self.assertEqual(found['status'],'Завершено в срок')
  self.call('hr/logout',{});self.assertEqual(self.call('hr')[0],401)
 def test_expired_deadline(self):
  c=self.call('start',{'name':'Проверка Просрочки'})[1]['candidate']
  with self.m.db() as db:db.execute('UPDATE candidates SET deadline=? WHERE id=?',(time.time()-10,c['id']))
  self.assertEqual(self.call('session')[1]['candidate']['status'],'Дедлайн истёк, обучение не завершено')
  for n in [1,2,3]:code,res=self.call('complete',{'block':n,'confirmed':True});self.assertEqual(code,200)
  self.assertEqual(res['candidate']['status'],'Завершено с просрочкой')
 def test_cross_origin_and_bearer(self):
  origin='https://skimirilov.github.io';self.m.ALLOWED_ORIGINS.add(origin)
  request=urllib.request.Request(self.url+'/api/start',data=json.dumps({'name':'Проверка Pages'}).encode(),headers={'Content-Type':'application/json','Origin':origin})
  with urllib.request.urlopen(request) as response:
   self.assertEqual(response.headers['Access-Control-Allow-Origin'],origin);token=json.load(response)['candidate']['id']
  request=urllib.request.Request(self.url+'/api/session',headers={'Authorization':'Bearer '+token,'Origin':origin})
  with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response)['candidate']['name'],'Проверка Pages')
  request=urllib.request.Request(self.url+'/api/start',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://untrusted.example'})
  with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
  self.assertEqual(error.exception.code,403)
  request=urllib.request.Request(self.url+'/api/hr',headers={'Authorization':'Bearer '+token})
  with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
  self.assertEqual(error.exception.code,401)
  request=urllib.request.Request(self.url+'/api/hr/login',data=json.dumps({'password':self.m.PASSWORD}).encode(),headers={'Content-Type':'application/json','Origin':origin})
  with urllib.request.urlopen(request) as response:admin_token=json.load(response)['token']
  request=urllib.request.Request(self.url+'/api/hr',headers={'Authorization':'Bearer '+admin_token,'Origin':origin})
  with urllib.request.urlopen(request) as response:self.assertIsInstance(json.load(response)['candidates'],list)
  request=urllib.request.Request(self.url+'/api/health',method='OPTIONS',headers={'Origin':origin,'Access-Control-Request-Headers':'Authorization'})
  with urllib.request.urlopen(request) as response:self.assertEqual(response.status,204)
if __name__=='__main__':unittest.main()
