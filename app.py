#!/usr/bin/env python3
"""Local job screening app, persisted in SQLite outside the downloaded package."""
import argparse,datetime as dt,fcntl,hashlib,json,os, secrets,shlex,sqlite3,sys,threading,time,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import board,sources
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('REMOTE_SWE_DATA_DIR',str(Path.home()/'.local/share/remote-swe-board')))
DATA.mkdir(parents=True,exist_ok=True)
REVISION=0
DB=DATA/'jobs.sqlite3';LOCK=threading.RLock();REFRESH_LOCK=threading.Lock();TOKEN=secrets.token_urlsafe(32)
state={'running':False,'message':'Ready','report':{},'last_attempt':0,'last_success':0};STATUSES=['New','Screening','Saved','Applied','Interview','Rejected','Not eligible','Archived']
def connect():
 c=sqlite3.connect(DB,timeout=30);c.execute('PRAGMA journal_mode=WAL');return c
def init():
 with connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, dedup TEXT, posted TEXT, data TEXT NOT NULL, status TEXT NOT NULL DEFAULT \'New\', comments TEXT NOT NULL DEFAULT \'\')')
  c.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
  r=c.execute("SELECT value FROM meta WHERE key='refresh'").fetchone()
  if r:state.update(json.loads(r[0]));state['running']=False
  count=c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
 if not count:
  seed=ROOT/'output/jobs.json'
  if seed.exists():
   save_rows(json.loads(seed.read_text()))
   seed_refresh=ROOT/'output/seed-refresh.json'
   if seed_refresh.exists():
    state.update(json.loads(seed_refresh.read_text()));state['running']=False
    with connect() as c:c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('refresh',json.dumps(state)))
def save_rows(rows):
 global REVISION
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 with LOCK,connect() as c:
  for row in rows:
   # Same company, role AND geography only. Different openings remain distinct.
   key='|'.join(row.get(f,'').strip().lower() for f in ['Company','Role','Location'])
   found=c.execute('SELECT id,data FROM jobs WHERE id=? OR dedup=? LIMIT 1',(row['Job ID'],key)).fetchone()
   identifier=found[0] if found else row['Job ID'];old=json.loads(found[1]) if found else {}
   row=dict(row);row['Job ID']=identifier;row['First seen']=old.get('First seen') or now;row['Last seen']=now
   # Reclassify bundled legacy rows too; missing descriptions require manual review.
   if row.get('Description'):
    classification,evidence=board.eligible(row.get('Location',''),row['Description'],row.get('Location','').lower()=='worldwide')
    if classification=='Excluded' or 'timezone' not in row.get('Eligibility evidence','').lower():row['Panama eligibility'],row['Eligibility evidence']=classification,evidence
   elif row.get('Panama eligibility')=='Confirmed':row['Panama eligibility']='Unclear';row['Eligibility evidence']='Legacy row lacks description; refresh before trusting location labels.'
   posted=row.get('Published at') or row.get('Posted') or ''
   c.execute('INSERT INTO jobs(id,dedup,posted,data,status,comments) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET dedup=excluded.dedup,posted=excluded.posted,data=excluded.data',(identifier,key,posted,json.dumps(row),row.get('Status','New'),''))
 with LOCK:REVISION+=1
def get_jobs():
 with LOCK,connect() as c:
  out=[]
  for identifier,raw,status,comments in c.execute('SELECT id,data,status,comments FROM jobs ORDER BY CASE WHEN posted="" THEN 1 ELSE 0 END,posted DESC,id DESC'):
   r=json.loads(raw);r['Status']=status;r['Comments']=comments;out.append(r)
 return out
def progress(message):
 with LOCK:state['message']=message
 print(message,flush=True)
def run_refresh(pages=100):
 if not REFRESH_LOCK.acquire(False):return False
 with LOCK:state['running']=True;state['last_attempt']=time.time();state['message']='Fetching remote jobs…'
 def worker():
  try:
   report=sources.refresh(save_rows,progress,pages)
   with LOCK:
    state['report']=report
    if report['sources']:state['last_success']=time.time()
    state['message']='Refresh finished'+(' — some sources failed; see coverage' if report['errors'] else '')
  except Exception as e:
   with LOCK:state['message']='Refresh failed: '+str(e)
  finally:
   with LOCK,connect() as c:
    state['running']=False;c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('refresh',json.dumps(state)))
   REFRESH_LOCK.release()
 threading.Thread(target=worker,daemon=True).start();return True
def scheduler():
 while True:
  if time.time()-state['last_attempt']>=86400:run_refresh()
  time.sleep(30)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def valid(self):
  host=self.headers.get('Host','')
  return host in ('127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port))
 def send(self,data,code=200,mime='application/json'):
  raw=data.encode() if isinstance(data,str) else json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if not self.valid():return self.send({'error':'Invalid host'},403)
  path=urllib.parse.urlsplit(self.path).path
  if path=='/':return self.send((ROOT/'ui.html').read_text().replace('__TOKEN__',TOKEN),mime='text/html')
  if path=='/health':return self.send({'app':'remote-swe-board','version':2})
  if path=='/api/state':return self.send({'refresh':dict(state),'revision':REVISION,'data_directory':str(DATA)})
  if path=='/api/jobs':return self.send({'jobs':get_jobs(),'refresh':dict(state),'revision':REVISION,'data_directory':str(DATA)})
  if path=='/api/backup':
   with LOCK,connect() as c:
    # JSON includes statuses and comments and can be restored from the app.
    return self.send({'version':2,'jobs':get_jobs(),'refresh':dict(state)})
  return self.send({'error':'Not found'},404)
 def do_POST(self):
  global REVISION
  if not self.valid() or self.headers.get('X-Board-Token')!=TOKEN:return self.send({'error':'Invalid session'},403)
  try:
   size=int(self.headers.get('Content-Length','0'))
   if size>30_000_000:return self.send({'error':'Payload too large'},413)
   payload=json.loads(self.rfile.read(size) or b'{}')
   if self.path=='/api/refresh':return self.send({'started':run_refresh()})
   if self.path=='/api/screen':
    if payload.get('status') not in STATUSES or not isinstance(payload.get('comments',''),str):return self.send({'error':'Invalid screening fields'},400)
    with LOCK,connect() as c:
     cursor=c.execute('UPDATE jobs SET status=?,comments=? WHERE id=?',(payload['status'],payload.get('comments','')[:20000],payload.get('id')))
     if not cursor.rowcount:return self.send({'error':'Job not found'},404)
     REVISION+=1
    return self.send({'saved':True})
   if self.path=='/api/restore':
    rows=payload.get('jobs',[])
    if not isinstance(rows,list) or any(not isinstance(r,dict) or not r.get('Job ID') for r in rows):return self.send({'error':'Invalid backup'},400)
    save_rows(rows)
    with LOCK,connect() as c:
     for r in rows:
      status=r.get('Status','New');status=status if status in STATUSES else 'New'
      key='|'.join(r.get(f,'').strip().lower() for f in ['Company','Role','Location'])
      match=c.execute('SELECT id FROM jobs WHERE id=? OR dedup=? LIMIT 1',(r['Job ID'],key)).fetchone()
      if match:c.execute('UPDATE jobs SET status=?,comments=? WHERE id=?',(status,str(r.get('Comments',''))[:20000],match[0]))
    return self.send({'restored':len(rows)})
   return self.send({'error':'Not found'},404)
  except (ValueError,KeyError,TypeError) as e:return self.send({'error':'Invalid request: '+str(e)},400)
def install():
 import shutil,subprocess
 apps=Path.home()/'.local/share/applications';apps.mkdir(parents=True,exist_ok=True)
 exec_line='"'+sys.executable.replace('"','\\"')+'" "'+str(ROOT/'app.py').replace('"','\\"')+'"'
 desktop='[Desktop Entry]\nType=Application\nName=Remote SWE Job Board\nComment=Screen remote jobs, save notes and track applications\nExec='+exec_line+'\nIcon=edit-find\nTerminal=false\nCategories=Office;\n'
 # Use a new desktop ID so GNOME discards launchers cached before a move.
 (apps/'remote-swe-board.desktop').unlink(missing_ok=True)
 path=apps/'org.local.RemoteSWEBoard.desktop'
 temporary=path.with_suffix('.desktop.tmp');temporary.write_text(desktop);temporary.chmod(0o755);temporary.replace(path)
 if shutil.which('update-desktop-database'):
  subprocess.run(['update-desktop-database',str(apps)],check=True)
 try:folder=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True).strip())
 except (OSError,subprocess.CalledProcessError):folder=Path.home()/'Desktop'
 if folder.is_dir():
  shortcut=folder/'Remote SWE Job Board.desktop';temporary=shortcut.with_suffix('.desktop.tmp');temporary.write_text(desktop);temporary.chmod(0o755);temporary.replace(shortcut)
  subprocess.run(['gio','set',str(shortcut),'metadata::trusted','true'],capture_output=True)
 print('Installed. Open Remote SWE Job Board from your applications menu. Keep this extracted folder in place.')
def open_browser(url):
 import subprocess
 subprocess.Popen(["xdg-open", url], start_new_session=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--install',action='store_true');p.add_argument('--no-browser',action='store_true');p.add_argument('--import-now',action='store_true');p.add_argument('--pages',type=int,default=100);p.add_argument('--port',type=int,default=8765);a=p.parse_args()
 if a.install:
  import subprocess
  install()
  with (DATA/'app.log').open('a') as log:
   subprocess.Popen([sys.executable,str(ROOT/'app.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  return
 init()
 if a.import_now:
  run_refresh(a.pages)
  while state['running']:time.sleep(.2)
  print(json.dumps({'rows':len(get_jobs()),'refresh':state},indent=2));return
 lock=(DATA/'app.lock').open('w')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:
  if not a.no_browser:open_browser('http://127.0.0.1:'+str(a.port))
  return
 try:server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
 except OSError:raise SystemExit(f'Port {a.port} is busy. Use --port with another port.')
 threading.Thread(target=scheduler,daemon=True).start()
 if not a.no_browser:threading.Timer(.5,lambda:open_browser('http://127.0.0.1:'+str(a.port))).start()
 print('Job board running at http://127.0.0.1:'+str(a.port),flush=True)
 server.serve_forever()
if __name__=='__main__':main()
