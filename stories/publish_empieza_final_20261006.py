import os, json, time
from pathlib import Path
import requests
token=os.environ['META_IG_ACCESS_TOKEN'].strip()
ig=os.environ['META_IG_USER_ID'].strip()
base='https://graph.instagram.com'
def api(method,path,data):
    response=requests.request(method,base+'/'+path,data=data if method=='POST' else None,params=data if method=='GET' else None,timeout=90)
    result=response.json()
    if 'error' in result:
        raise RuntimeError(result['error'].get('message','Instagram API error'))
    response.raise_for_status()
    return result
account=api('GET',ig,{'fields':'username','access_token':token})
if account.get('username')!='berme.energy':
    raise RuntimeError('Account does not match berme.energy')
print('Account confirmed: berme.energy',flush=True)
results=[]
for number in range(1,6):
    url=f"https://raw.githubusercontent.com/joselu392/berme-energy-automation/{os.environ['GITHUB_SHA']}/docs/empieza-final-20261006/{number:02d}.jpg"
    ready=False
    for attempt in range(20):
        if requests.get(url,timeout=30).status_code==200:
            ready=True;break
        time.sleep(3)
    if not ready:raise RuntimeError('Public image unavailable')
    container=api('POST',ig+'/media',{'media_type':'STORIES','image_url':url,'access_token':token})['id']
    for attempt in range(40):
        state=api('GET',container,{'fields':'status_code','access_token':token}).get('status_code')
        if state=='FINISHED':break
        if state in ('ERROR','EXPIRED'):raise RuntimeError('Media processing failed')
        time.sleep(3)
    else:raise RuntimeError('Media processing timed out')
    published=api('POST',ig+'/media_publish',{'creation_id':container,'access_token':token})
    if not published.get('id'):raise RuntimeError('Missing published media id')
    results.append({'story':number,'media_id':published['id']})
    Path('publication.json').write_text(json.dumps({'username':'berme.energy','results':results},indent=2))
    print('STORY PUBLISHED',number,published['id'],flush=True)
    time.sleep(5)
print('ALL 4 STORIES AND COVER PUBLISHED',flush=True)
