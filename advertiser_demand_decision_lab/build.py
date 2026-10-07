"""Build deterministic analysis and standalone offline dashboard. Python 3.11+."""
from pathlib import Path
import hashlib,json
import lab
ROOT=Path(__file__).resolve().parent
def main():
 out=ROOT/'output';data=lab.build(out)
 text=(ROOT/'dashboard.html').read_text(encoding='utf-8')
 payload=json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).replace('</','<\\/')
 assert text.count('__DATA__')==1
 (out/'dashboard.html').write_text(text.replace('__DATA__',payload),encoding='utf-8')
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name not in ('manifest.json','CASE_STUDY.pdf')}
 (out/'manifest.json').write_text(json.dumps({'synthetic':True,'seed':data['seed'],'as_of':data['as_of'],'files':files},indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'scenarios':len(data['scenarios']),'views':len(data['views']),'dashboard':str(out/'dashboard.html')}))
if __name__=='__main__':main()
