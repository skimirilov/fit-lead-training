#!/usr/bin/env python3
import os,json,sqlite3,secrets,time,hashlib,hmac,csv,io
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from http.cookies import SimpleCookie
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('FIT_DATA',ROOT/'data'));DATA.mkdir(exist_ok=True)
DB=DATA/'training.sqlite3'
KEY=DATA/'hr-password.txt'
if not KEY.exists():KEY.write_text(secrets.token_urlsafe(14));KEY.chmod(0o600)
PASSWORD=os.environ.get('FIT_HR_PASSWORD',KEY.read_text().strip())
ALLOWED_ORIGINS={v.strip().rstrip('/') for v in os.environ.get('FIT_ALLOWED_ORIGINS','').split(',') if v.strip()}
PRODUCTION=os.environ.get('FIT_PRODUCTION')=='1'
if PRODUCTION and len(os.environ.get('FIT_HR_PASSWORD',''))<16:raise RuntimeError('Set FIT_HR_PASSWORD to at least 16 characters')
DATABASE_URL=os.environ.get('DATABASE_URL','')
if PRODUCTION and not DATABASE_URL:raise RuntimeError('Production requires persistent PostgreSQL DATABASE_URL')
class PostgresDB:
 def __init__(self):
  import psycopg
  from psycopg.rows import dict_row
  self.connection=psycopg.connect(DATABASE_URL,row_factory=dict_row,connect_timeout=15)
 def __enter__(self):return self
 def __exit__(self,kind,value,tb):
  try:
   if kind:self.connection.rollback()
   else:self.connection.commit()
  finally:self.connection.close()
 def execute(self,sql,params=()):return self.connection.execute(sql.replace('?','%s'),params)
 def executescript(self,sql):
  for statement in sql.split(';'):
   if statement.strip():self.connection.execute(statement.replace(' REAL',' DOUBLE PRECISION'))
def db():
 if DATABASE_URL:return PostgresDB()
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
with db() as c:
 c.executescript('CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,name TEXT NOT NULL,created REAL NOT NULL,start REAL NOT NULL,deadline REAL NOT NULL,b1 REAL,b2 REAL,b3 REAL,feedback TEXT);CREATE TABLE IF NOT EXISTS admins(token TEXT PRIMARY KEY,expires REAL);')
def state(row):
 d=dict(row);n=sum(d['b'+str(i)] is not None for i in range(1,4));d['progress']=[0,33,67,100][n];d['completed']=n;end=d['b3'];d['duration']=(end or time.time())-d['start'];d['status']=('Завершено в срок' if end<=d['deadline'] else 'Завершено с просрочкой') if end else ('Дедлайн истёк, обучение не завершено' if time.time()>d['deadline'] else 'В процессе');return d
ATTEMPTS={}
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'web'),**kw)
 def log_message(self,fmt,*args):pass
 def cookies(self):
  c=SimpleCookie();c.load(self.headers.get('Cookie',''));return {k:v.value for k,v in c.items()}
 def send(self,obj,code=200,cookie=None,ctype='application/json; charset=utf-8'):
  b=json.dumps(obj,ensure_ascii=False).encode() if ctype.startswith('application/json') else obj.encode('utf-8-sig');self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','same-origin')
  origin=self.headers.get('Origin','')
  if origin in ALLOWED_ORIGINS:self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
  if cookie:self.send_header('Set-Cookie',cookie+'; HttpOnly; SameSite=Strict; Path=/'+('; Secure' if PRODUCTION else ''))
  self.end_headers();self.wfile.write(b)
 def auth_token(self,cookie):
  auth=self.headers.get('Authorization','')
  return auth[7:] if auth.startswith('Bearer ') else self.cookies().get(cookie,'')
 def candidate(self,c):return c.execute('SELECT * FROM candidates WHERE id=?',(self.auth_token('fit_session'),)).fetchone()
 def admin(self,c):return c.execute('SELECT 1 FROM admins WHERE token=? AND expires>?',(self.auth_token('fit_hr'),time.time())).fetchone()
 def do_GET(self):
  path=self.path.split('?')[0]
  if path.startswith('/api/'):
   with db() as c:
    if path=='/api/health':return self.send({'ok':True})
    if path=='/api/session':
     r=self.candidate(c);return self.send({'candidate':state(r) if r else None,'serverTime':time.time()})
    if path in ['/api/hr','/api/export']:
     if not self.admin(c):return self.send({'error':'Войдите в HR-панель'},401)
     rows=[state(r) for r in c.execute('SELECT * FROM candidates ORDER BY created DESC')]
     if path=='/api/hr':return self.send({'candidates':rows})
     f=io.StringIO();raw_writer=csv.writer(f)
     class SafeWriter:
      def writerow(self,values):raw_writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in values])
     w=SafeWriter();w.writerow(['ФИО','Статус','Прогресс','Создан','Начало','Дедлайн','Блок 1','Блок 2','Блок 3 / завершение','Длительность, ч','Отзыв'])
     for r in rows:w.writerow([r['name'],r['status'],r['progress']]+[time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(r[k])) if r[k] else '' for k in ['created','start','deadline','b1','b2','b3']]+[round(r['duration']/3600,2),r['feedback'] or ''])
     return self.send(f.getvalue(),ctype='text/csv; charset=utf-8')
    return self.send({'error':'Не найдено'},404)
  if path=='/hr':
   self.send_response(302);self.send_header('Location','/hr/');self.end_headers();return
  if path in ['/','/training','/success','/finish']:self.path='/index.html'
  return super().do_GET()
 def do_OPTIONS(self):
  if self.headers.get('Origin','') not in ALLOWED_ORIGINS:return self.send({'error':'Недопустимый источник запроса'},403)
  self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Vary','Origin');self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization');self.send_header('Access-Control-Max-Age','600');self.end_headers()
 def do_POST(self):
  origin=self.headers.get('Origin');host=self.headers.get('Host')
  if origin and origin not in ALLOWED_ORIGINS and origin not in ['http://'+host,'https://'+host]:return self.send({'error':'Недопустимый источник запроса'},403)
  try:
   size=int(self.headers.get('Content-Length',0))
   if size>12000:return self.send({'error':'Слишком длинный запрос'},413)
   v=json.loads(self.rfile.read(size) or '{}')
  except (ValueError,UnicodeError):return self.send({'error':'Некорректный запрос'},400)
  with db() as c:
   p=self.path
   if p=='/api/hr/login':
    ip=self.client_address[0];recent=[t for t in ATTEMPTS.get(ip,[]) if time.time()-t<300];ATTEMPTS[ip]=recent
    if len(recent)>=10:return self.send({'error':'Слишком много попыток. Повторите через 5 минут.'},429)
    if not hmac.compare_digest(str(v.get('password','')),PASSWORD):recent.append(time.time());return self.send({'error':'Неверный пароль'},401)
    token=secrets.token_urlsafe(32);c.execute('INSERT INTO admins VALUES (?,?)',(token,time.time()+28800));return self.send({'ok':True,'token':token},cookie='fit_hr='+token)
   if p=='/api/hr/logout':c.execute('DELETE FROM admins WHERE token=?',(self.auth_token('fit_hr'),));return self.send({'ok':True},cookie='fit_hr=; Max-Age=0')
   if p=='/api/start':
    r=self.candidate(c)
    if r:return self.send({'candidate':state(r)})
    name=' '.join(str(v.get('name','')).split())
    if len(name)<5 or len(name)>160 or len(name.split())<2:return self.send({'error':'Укажите фамилию и имя, при наличии — отчество'},400)
    token=secrets.token_urlsafe(32);now=time.time();c.execute('INSERT INTO candidates(id,name,created,start,deadline) VALUES (?,?,?,?,?)',(token,name,now,now,now+72*3600));r=c.execute('SELECT * FROM candidates WHERE id=?',(token,)).fetchone();return self.send({'candidate':state(r)},cookie='fit_session='+token+'; Max-Age=31536000')
   if p=='/api/restore':
    token=str(v.get('code','')).strip();r=c.execute('SELECT * FROM candidates WHERE id=?',(token,)).fetchone()
    if not r:return self.send({'error':'Код не найден. Проверьте код восстановления.'},404)
    return self.send({'candidate':state(r)},cookie='fit_session='+token+'; Max-Age=31536000')
   r=self.candidate(c)
   if not r:return self.send({'error':'Сначала начните обучение'},401)
   if p=='/api/complete':
    n=v.get('block')
    if type(n)!=int or n not in [1,2,3]:return self.send({'error':'Некорректный блок'},400)
    if n>1 and not r['b'+str(n-1)]:return self.send({'error':'Сначала завершите предыдущий блок'},409)
    if v.get('confirmed') is not True:return self.send({'error':'Подтвердите просмотр видео'},400)
    c.execute('UPDATE candidates SET b%d=COALESCE(b%d,?) WHERE id=?'%(n,n),(time.time(),r['id']));r=c.execute('SELECT * FROM candidates WHERE id=?',(r['id'],)).fetchone();return self.send({'candidate':state(r)})
   if p=='/api/feedback':
    if not r['b3']:return self.send({'error':'Сначала завершите обучение'},409)
    msg=str(v.get('text','')).strip()
    if not msg or len(msg)>4000:return self.send({'error':'Напишите отзыв до 4000 символов'},400)
    c.execute('UPDATE candidates SET feedback=? WHERE id=?',(msg,r['id']));return self.send({'ok':True})
   return self.send({'error':'Не найдено'},404)
if __name__=='__main__':
 print('Fit&Lead: http://127.0.0.1:8000',flush=True)
 ThreadingHTTPServer((os.environ.get('FIT_HOST','127.0.0.1'),int(os.environ.get('PORT',8000))),Handler).serve_forever()
