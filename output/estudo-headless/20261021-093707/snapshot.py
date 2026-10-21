"""Manifesto sem conteúdo de ambiente nem linhas de comando de processos."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def ps(script):
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script],
                            capture_output=True, text=True, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(result.stdout.strip() or '[]')

def snapshot():
    files = list((ROOT/'app').rglob('*.py')) + list((ROOT/'tests').rglob('*.py'))
    files += [p for p in (ROOT/'tests'/'fixtures').rglob('*') if p.is_file()]
    files += [ROOT/p for p in ('main.py', 'requirements.txt', '.env.example', 'Dockerfile', '.gitignore')]
    processes = ps("@(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe','chrome.exe','node.exe') } | Select-Object ProcessId,ParentProcessId,Name,CreationDate) | ConvertTo-Json -Depth 4 -Compress")
    listeners = ps("@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -ge 8000 -and $_.LocalPort -le 8010 } | Select-Object LocalAddress,LocalPort,OwningProcess) | ConvertTo-Json -Compress")
    chrome = ps("(Get-Item -LiteralPath 'C:/Program Files/Google/Chrome/Application/chrome.exe').VersionInfo.ProductVersion | ConvertTo-Json -Compress")
    return dict(time=datetime.now().astimezone().isoformat(), python=sys.version,
                playwright=importlib.metadata.version('playwright'), chrome=chrome,
                commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
                hashes={str(p.relative_to(ROOT)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))},
                processes=processes, listeners=listeners)

if __name__ == '__main__':
    target = OUT/(sys.argv[1]+'.json')
    data = snapshot()
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(file=str(target), files=len(data['hashes']), chrome=data['chrome'], listeners=data['listeners'])))
