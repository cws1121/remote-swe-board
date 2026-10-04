"""Feed adapters. Each batch is saved immediately by the local app."""
import concurrent.futures,json,time,urllib.parse
import board

def convert_himalayas(j):
 locations=j.get('locationRestrictions'); loc=', '.join(x.get('name',x.get('alpha2','')) if isinstance(x,dict) else x for x in (locations or []))
 salary=f"{j.get('currency','')} {j.get('minSalary') or '?'}–{j.get('maxSalary') or '?'} / {j.get('salaryPeriod') or 'annual'}" if j.get('minSalary') or j.get('maxSalary') else ''
 return board.row(j['title'],j['companyName'],loc or ('Worldwide' if locations==[] else ''),j.get('description',''),'Himalayas',j['applicationLink'],j.get('pubDate'),salary,locations==[],j.get('expiryDate'),j.get('timezoneRestrictions'),seniority=j.get('seniority'))
def himalayas_search(save,progress,max_pages=100):
 total=0; scanned=0
 def fetch_page(query,page):
  params=urllib.parse.urlencode({'q':query,'sort':'recent','page':page})
  return page,json.loads(board.request('https://himalayas.app/jobs/api/search?'+params))
 for query in ['software engineer','developer']:
  seen=set();finished=False
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   for first in range(1,max_pages+1,4):
    batch=[pool.submit(fetch_page,query,page) for page in range(first,min(first+4,max_pages+1))]
    for future in batch:
     page,data=future.result();jobs=data.get('jobs',[]);scanned+=1
     fingerprint=tuple(j.get('guid') or j.get('applicationLink') for j in jobs)
     if not jobs or fingerprint in seen:finished=True;continue
     seen.add(fingerprint);rows=[r for j in jobs if (r:=convert_himalayas(j))];save(rows);total+=len(rows)
     progress(f'Himalayas: {query}, page {page}, {total} SWE rows processed')
     if page*(data.get('limit') or 20)>=data.get('totalCount',5000):finished=True
    if finished:break
    time.sleep(.5)
 return {'source':'Himalayas','processed_swe_rows':total,'pages_scanned':scanned,'pages_per_search_limit':max_pages,'coverage':'Two keyword searches; max 2,000 raw results each per daily import. Not all remote jobs.'}
def remotive(save,progress):
 data=json.loads(board.request('https://remotive.com/api/remote-jobs?category=software-dev'));rows=[]
 for j in data.get('jobs',[]):
  r=board.row(j['title'],j.get('company_name',''),j.get('candidate_required_location',''),j.get('description',''),'Remotive',j['url'],j.get('publication_date'),j.get('salary',''),sourceurl=j['url'])
  if r:rows.append(r)
 save(rows);progress(f'Remotive: {len(rows)} SWE jobs');return {'source':'Remotive','swe_rows':len(rows),'coverage':'Public software development feed; delayed by source.'}
def jobicy(save,progress):
 rows=[];cursor=None;seen=set()
 for page in range(20):
  params={'count':200,'industry':'engineering'}
  if cursor:params['cursor']=cursor
  data=json.loads(board.request('https://jobicy.com/api/v2/remote-jobs?'+urllib.parse.urlencode(params)))
  if data.get('success') is False:raise RuntimeError(str(data.get('error','Source returned an error')))
  for j in data.get('jobs',[]):
   sal=f"{j.get('salaryCurrency','')} {j.get('salaryMin') or '?'}–{j.get('salaryMax') or '?'} / {j.get('salaryPeriod') or 'unspecified'}" if j.get('salaryMin') or j.get('salaryMax') else ''
   r=board.row(j['jobTitle'],j.get('companyName',''),j.get('jobGeo',''),j.get('jobDescription',''),'Jobicy',j['url'],j.get('pubDate'),sal,world=j.get('jobGeo','').lower()=='anywhere',seniority=j.get('jobLevel',''))
   if r:rows.append(r)
  save(rows);rows=[];progress(f'Jobicy: page {page+1}')
  cursor=data.get('nextCursor')
  if not cursor or cursor in seen:break
  seen.add(cursor);time.sleep(.5)
 return {'source':'Jobicy','pages':page+1,'coverage':'Available recent public feed; limited by source window.'}
def refresh(save,progress,max_pages=100):
 def old_source(fn):
  rows,meta=fn();save(rows);progress(f"{meta['source']}: {len(rows)} SWE jobs");return meta
 tasks={'Himalayas':lambda:himalayas_search(save,progress,max_pages),'Remotive':lambda:remotive(save,progress),'Jobicy':lambda:jobicy(save,progress),'Remote OK':lambda:old_source(board.remoteok),'We Work Remotely':lambda:old_source(board.wwr)}
 report={'sources':[],'errors':[]}
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
  futures={pool.submit(fn):name for name,fn in tasks.items()}
  for f in concurrent.futures.as_completed(futures):
   try:report['sources'].append(f.result())
   except Exception as e:report['errors'].append({'source':futures[f],'error':str(e)});progress(f'{futures[f]} unavailable: {e}')
 return report
