#!/usr/bin/env python3
"""Remote SWE aggregator. Python 3.10+, standard library only."""
import argparse, concurrent.futures, csv, datetime as dt, hashlib, html, json, os, re, sys, time
import urllib.request, urllib.error, urllib.parse, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent
UTC = dt.timezone.utc
TECH = {'Angular':r'\bangular\b','.NET':r'\.net\b|\bdotnet\b|\bc#','Playwright':r'\bplaywright\b','CI/CD':r'ci/cd|github actions|teamcity','SQL Server':r'sql server','TypeScript':r'\btypescript\b','Azure':r'\bazure\b'}
FIELDS = ['Description','Published at','Role','Company','Location','Panama eligibility','Eligibility evidence','Seniority','Tech stack','Salary','Posted','Expires','Source','Apply link','Source link','Job ID','Status','First seen','Last seen']
def request(url, payload=None, headers=None, method=None):
    h = {'User-Agent':'PersonalRemoteSWEBoard/1.0','Accept':'application/json'}
    h.update(headers or {})
    data = None if payload is None else json.dumps(payload).encode()
    if data: h['Content-Type']='application/json'
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=h,method=method),timeout=35) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==2: raise RuntimeError(f'HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}') from None
            time.sleep(min(float(e.headers.get('Retry-After','2')),10)*(attempt+1))
        except (OSError, TimeoutError):
            if attempt==2: raise
            time.sleep(2)
def text(s): return html.unescape(re.sub('<[^>]+>',' ',str(s or '')))
def date(s):
    if not s: return ''
    try:
        if isinstance(s,(int,float)): return dt.datetime.fromtimestamp(s/1000 if s>1e11 else s,UTC).date().isoformat()
        return dt.datetime.fromisoformat(str(s).replace('Z','+00:00')).date().isoformat()
    except (ValueError,OverflowError):
        try: return parsedate_to_datetime(str(s)).date().isoformat()
        except (ValueError,TypeError): return ''
def canonical(url):
    p=urllib.parse.urlsplit(url or '')
    return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/'),urllib.parse.urlencode([(k,v) for k,v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(('utm_','ref'))]),''))
def eligible(location, description, world=False, timezone=None):
    low=location.lower(); desc=description.lower()
    authorization = re.search(r'(?:must|required|need|have to|should)[^.\n]{0,100}(?:work legally|legally (?:work|authorized)|(?:work|employment) authori[sz]ation|right to work)[^.\n]{0,80}(?:united states|\bus\b|\busa\b)|(?:authorized|eligible|legally able|legal right|authorization)[^.\n]{0,80}(?:work|employment)[^.\n]{0,50}(?:united states|\bus\b|\busa\b)|(?:us|u\.s\.|united states) (?:citizen|citizenship|work authorization)|(?:must|requires?|active)[^.\n]{0,60}security clearance|security clearance (?:is )?required',desc)
    if authorization: return 'Excluded','Work authorization / clearance restriction: '+authorization.group(0)
    restriction = re.search(r'\b(?:us|usa|united states|uk|united kingdom|canada|europe|eu)[ -]only\b|must (?:be (?:based|located)|reside|live) in (?:the )?(?:united states|usa|uk|canada)',desc)
    if restriction: return 'Excluded', 'Description restriction: '+restriction.group(0)
    if timezone and not any(str(x).replace('UTC','').strip() in ('-5','-5.0','-05:00') for x in timezone): return 'Unclear','Timezone restrictions require review: '+str(timezone)
    if re.search(r'\bpanama\b',low): return 'Confirmed','Source explicitly lists Panama; verify employer requirements.'
    if world or re.search(r'worldwide|anywhere in the world|\bglobal\b',low): return 'Confirmed','Source labels this worldwide; verify employer requirements.'
    if re.search(r'latam|latin america|south america|north america|central america|americas',low): return 'Unclear','Regional label; Panama eligibility needs confirmation.'
    if low.strip() in ('','remote','anywhere'): return 'Unclear','No explicit eligible-country list.'
    return 'Excluded','Source lists location restrictions without Panama.'
def row(role,company,location,desc,source,url,posted='',salary='',world=False,expires='',timezone=None,sourceurl='',seniority=''):
    if not re.search(r'software|developer|full[ -]?stack|front[ -]?end|back[ -]?end|\bswe\b|(?:platform|web|test automation|qa automation|sdet|devops).*engineer',role,re.I): return None
    if re.search(r'intern|\bjunior\b|\bnew grad\b|entry.level',role,re.I): level='Junior'
    elif re.search(r'senior|\bsr\.?\b|staff|principal|lead',role,re.I) or 'Senior' in str(seniority): level='Senior+'
    else: level='Unspecified'
    desc=text(desc); el,evidence=eligible(location,desc,world,timezone)
    url=canonical(url)
    if not url.startswith(('https://','http://')): return None
    try:
        published = dt.datetime.fromtimestamp(posted/1000 if posted>1e11 else posted,UTC).isoformat() if isinstance(posted,(int,float)) else dt.datetime.fromisoformat(str(posted).replace('Z','+00:00')).isoformat()
    except (ValueError,TypeError,OverflowError):
        try: published=parsedate_to_datetime(str(posted)).isoformat()
        except (ValueError,TypeError): published=''
    return dict(zip(FIELDS,[desc,published,role,company,location or 'Not specified',el,evidence,level,', '.join(k for k,p in TECH.items() if re.search(p,desc+' '+role,re.I)),salary, date(posted),date(expires),source,url,canonical(sourceurl or url),hashlib.sha256(url.encode()).hexdigest()[:24],'New','','']))
def himalayas(pages):
    result=[]; cursor=None
    for page in range(pages):
        params={'limit':20}
        if cursor: params['cursor']=cursor
        data=json.loads(request('https://himalayas.app/jobs/api?'+urllib.parse.urlencode(params)))
        for j in data['jobs']:
            locations=j.get('locationRestrictions'); loc=', '.join(x.get('name',x.get('alpha2','')) if isinstance(x,dict) else x for x in (locations or []))
            sal=''
            if j.get('minSalary') or j.get('maxSalary'): sal=f"{j.get('currency','')} {j.get('minSalary') or '?'}–{j.get('maxSalary') or '?'} / {j.get('salaryPeriod') or 'annual'}"
            r=row(j['title'],j['companyName'],loc or ('Worldwide' if locations==[] else ''),j.get('description',''),'Himalayas',j['applicationLink'],j.get('pubDate'),sal,locations==[],j.get('expiryDate'),j.get('timezoneRestrictions'),seniority=j.get('seniority'))
            if r: result.append(r)
        cursor=data.get('nextCursor')
        if not cursor: break
        time.sleep(.2)
    return result, {'source':'Himalayas','pages':page+1,'more_available':bool(cursor),'total_feed_count':data.get('totalCount'),'note':'Browse feed includes non-SWE roles; use --pages 0 for a full crawl.'}
def remoteok():
    result=[]
    for j in json.loads(request('https://remoteok.com/api')):
        if not j.get('position'): continue
        salary=f"USD {j.get('salary_min') or '?'}–{j.get('salary_max') or '?'} / annual" if j.get('salary_min') or j.get('salary_max') else ''
        r=row(j['position'],j.get('company',''),j.get('location',''),j.get('description',''),'Remote OK',j.get('apply_url') or j.get('url'),j.get('date'),salary,sourceurl=j.get('url'))
        if r: result.append(r)
    return result, {'source':'Remote OK','note':'Current public feed window, not complete historical coverage.'}
def wwr():
    result=[]
    for cat in ['full-stack','front-end','back-end']:
        root=ET.fromstring(request(f'https://weworkremotely.com/categories/remote-{cat}-programming-jobs.rss'))
        for j in root.findall('.//item'):
            title=j.findtext('title',''); company,sep,role=title.partition(': ')
            if not sep: role=title; company=''
            desc=j.findtext('description',''); region=next((x.text for x in j if x.tag.split('}')[-1]=='region'), '') or ''
            # RSS location is not always supplied; keep missing restrictions unclear.
            r=row(role,company,region,desc,'We Work Remotely',j.findtext('link',''),j.findtext('pubDate',''),sourceurl=j.findtext('link',''))
            if r: result.append(r)
    return result, {'source':'We Work Remotely','note':'Three programming RSS feeds; missing location labels stay Unclear.'}
def merge(old,new):
    by={r['Job ID']:r for r in old}; keys={(r['Company'].strip().lower(),r['Role'].strip().lower(),r['Location'].strip().lower()):k for k,r in by.items()}; today=dt.datetime.now(UTC).date().isoformat()
    for r in new:
        key=(r['Company'].strip().lower(),r['Role'].strip().lower(),r['Location'].strip().lower()); identifier=r['Job ID']
        existing=by.get(identifier) or by.get(keys.get(key))
        if existing:
            r['Job ID']=existing['Job ID'];r['Status']=existing.get('Status','New'); r['First seen']=existing.get('First seen') or today
        else: r['First seen']=today
        r['Last seen']=today; by[r['Job ID']]=r;keys[key]=r['Job ID']
    return sorted(by.values(),key=lambda r:(r['Posted'] or r['First seen']),reverse=True)
def write_output(rows,report):
    out=ROOT/'output';out.mkdir(exist_ok=True)
    (out/'jobs.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (out/'run-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (out/'jobs.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    template=(ROOT/'template.html').read_text()
    blob=json.dumps(rows).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    (out/'jobs.html').write_text(template.replace('__JOBS__',blob).replace('__REPORT__',html.escape(json.dumps(report))),encoding='utf-8')
def notion_api(path,payload=None,method=None):
    token=os.environ.get('NOTION_TOKEN')
    if not token: raise RuntimeError('Set NOTION_TOKEN locally. Do not paste your token into chat.')
    time.sleep(.35)
    return json.loads(request('https://api.notion.com/v1/'+path,payload,{'Authorization':'Bearer '+token,'Notion-Version':'2025-09-03'},method))
def rich(value): return [{'text':{'content':str(value)[:1900]}}] if value else []
def setup_notion(page):
    schema={f:({'title':{}} if f=='Role' else {'url':{}} if f in ('Apply link','Source link') else {'select':{'options':[{'name':s} for s in ['New','Saved','Applied','Interview','Rejected','Archived']]}} if f=='Status' else {'rich_text':{}}) for f in FIELDS}
    response=notion_api('databases',{'parent':{'type':'page_id','page_id':page},'title':rich('Remote SWE Job Board'),'initial_data_source':{'properties':schema},'description':rich('Personal remote job listing. Sources: Himalayas https://himalayas.app, Remote OK https://remoteok.com, We Work Remotely https://weworkremotely.com. Eligibility is a source label, not employer verification.')})
    source=response['data_sources'][0]['id'];(ROOT/'notion-config.json').write_text(json.dumps({'data_source_id':source,'database_url':response.get('url','')},indent=2))
    print('Created Notion database:',response.get('url',''));return source
def sync_notion(rows):
    source=os.environ.get('NOTION_DATA_SOURCE_ID') or json.loads((ROOT/'notion-config.json').read_text())['data_source_id']
    existing={};cursor=None
    while True:
        response=notion_api(f'data_sources/{source}/query',{'page_size':100,**({'start_cursor':cursor} if cursor else {})})
        for p in response['results']:
            key=''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in p['properties'].get('Job ID',{}).get('rich_text',[]))
            if key: existing[key]=p['id']
        if not response.get('has_more'): break
        cursor=response['next_cursor']
    for r in rows:
        # Never overwrite application status, notes, or page contents on an existing row.
        props={f:({'title':rich(r[f])} if f=='Role' else {'url':r[f] or None} if f in ('Apply link','Source link') else {'rich_text':rich(r[f])}) for f in FIELDS if f!='Status'}
        if r['Job ID'] in existing: notion_api('pages/'+existing[r['Job ID']],{'properties':props},'PATCH')
        else:
            props['Status']={'select':{'name':'New'}}
            response=notion_api('pages',{'parent':{'type':'data_source_id','data_source_id':source},'properties':props});existing[r['Job ID']]=response['id']
    print('Notion sync complete:',len(rows),'rows')
def main():
    p=argparse.ArgumentParser();p.add_argument('--pages',type=int,default=50,help='Himalayas pages of 20; 0 = full crawl');p.add_argument('--notion-setup',metavar='PARENT_PAGE_ID');p.add_argument('--sync-notion',action='store_true');p.add_argument('--export-only',action='store_true');a=p.parse_args()
    path=ROOT/'output/jobs.json';old=json.loads(path.read_text()) if path.exists() else []; report={'updated':dt.datetime.now(UTC).isoformat(),'sources':[],'errors':[]}
    if a.notion_setup: setup_notion(a.notion_setup)
    if a.export_only: rows=old
    else:
        jobs=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            tasks={pool.submit(fn):name for name,fn in [('Himalayas',lambda:himalayas(a.pages or 1000000)),('Remote OK',remoteok),('We Work Remotely',wwr)]}
            for future in concurrent.futures.as_completed(tasks):
                try:
                    data,meta=future.result();jobs.extend(data);meta['swe_rows']=len(data);report['sources'].append(meta);print(meta,flush=True)
                except Exception as e: report['errors'].append({'source':tasks[future],'error':str(e)});print(tasks[future], 'failed:',str(e),file=sys.stderr)
        rows=merge(old,jobs)
    report['rows']=len(rows);write_output(rows,report)
    if a.sync_notion: sync_notion(rows)
    print('Open:',ROOT/'output/jobs.html')
    if report['errors']: sys.exit(1)
if __name__=='__main__': main()
