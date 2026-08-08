from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .analysis import analyze_repository


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the local browser interface."""
    server = ThreadingHTTPServer((host, port), DebuggingTimeMachineHandler)
    print(f"Debugging Time Machine is running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Debugging Time Machine.")
    finally:
        server.server_close()


def analyze_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an API payload and run analysis."""
    repo = _required(payload, "repo")
    good = _required(payload, "good")
    bad = _required(payload, "bad")
    test_cmd = _required(payload, "test_cmd")
    output_format = str(payload.get("format", "markdown") or "markdown").lower()
    if output_format not in {"markdown", "json"}:
        raise ValueError("format must be markdown or json")

    result = analyze_repository(repo, good, bad, test_cmd, output_format)
    suspect = result["suspect"]
    return {
        "report": result["report"],
        "explanation": result["explanation"],
        "suspect": _candidate_to_dict(suspect) if suspect is not None else None,
        "candidates": [_candidate_to_dict(candidate) for candidate in result["candidates"]],
    }


APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Debugging Time Machine — Neon</title>
    <style>
        :root{
            --bg:#041007; --panel:#07120b; --glass:rgba(255,255,255,0.02); --neon:#00ff7a; --neon-2:#00d27a; --muted:#98e9c5;
            --card-shadow: 0 20px 50px rgba(2,8,6,0.6);
            --mono: "Cascadia Code", Consolas, monospace;
        }
        html,body{height:100%;margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial;background:radial-gradient(1200px 600px at 10% 10%, rgba(0,255,122,0.06), transparent), linear-gradient(180deg,#02120a 0%, #041007 100%);color:var(--muted)}
        .app{min-height:100vh;display:flex;flex-direction:column}
        header{display:flex;align-items:center;justify-content:space-between;padding:20px 36px}
        .logo{display:flex;gap:14px;align-items:center}
        .logo .mark{width:52px;height:52px;border-radius:10px;background:linear-gradient(135deg,var(--neon),var(--neon-2));display:flex;align-items:center;justify-content:center;color:#03100a;font-weight:800;box-shadow:0 8px 40px rgba(0,255,122,0.08);font-family:var(--mono)}
        h1{margin:0;font-size:20px;color:#e6fff6}
        main{display:grid;grid-template-columns:380px 1fr;gap:28px;padding:28px}

        /* left control card */
        .card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border:1px solid rgba(0,255,122,0.06);border-radius:14px;padding:18px;box-shadow:var(--card-shadow);backdrop-filter: blur(6px);transition:transform .24s ease}
        .left .card{transform-style:preserve-3d}
        label{display:block;color:var(--muted);font-size:13px;margin-bottom:8px}
        input,textarea,select{width:100%;padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,0.03);background:transparent;color:#e6fff6;font-size:14px}
        textarea{min-height:96px}
        .row{display:flex;gap:10px;align-items:center}
        .btn{display:inline-flex;align-items:center;justify-content:center;padding:12px 16px;border-radius:10px;background:linear-gradient(90deg,var(--neon),var(--neon-2));color:#00120a;border:0;font-weight:800;cursor:pointer;box-shadow:0 12px 30px rgba(0,255,122,0.12);letter-spacing:0.6px}

        /* right side */
        .metrics{display:flex;gap:14px}
        .metric{flex:1;padding:14px;border-radius:12px;background:linear-gradient(180deg, rgba(0,0,0,0.3), rgba(255,255,255,0.02));border:1px solid rgba(0,255,122,0.04);min-height:76px;display:flex;flex-direction:column;justify-content:center;transform-style:preserve-3d}
        .metric .k{font-size:12px;color:#98e9c5}
        .metric .v{font-weight:800;font-size:16px;color:#dfffe9;margin-top:6px}

        .report{margin-top:12px;padding:18px;border-radius:12px;background:linear-gradient(180deg, rgba(0,0,0,0.32), rgba(0,0,0,0.2));border:1px solid rgba(0,255,122,0.03);min-height:420px;box-shadow:0 20px 50px rgba(0,0,0,0.6);position:relative;perspective:1200px}
        .report-inner{background:linear-gradient(180deg, rgba(3,8,6,0.55), rgba(0,0,0,0.4));border-radius:10px;padding:16px;color:#bfffe0;font-family:var(--mono);min-height:360px;overflow:auto;transform-style:preserve-3d;transition:transform .18s linear}

        /* tilt effect */
        .tilt{transform:rotateX(0deg) rotateY(0deg)}
        .float{animation:floaty 6s ease-in-out infinite}
        @keyframes floaty{0%{transform:translateY(0)}50%{transform:translateY(-8px)}100%{transform:translateY(0)}}

        .glow{position:absolute;right:24px;top:-40px;width:220px;height:120px;border-radius:50%;filter:blur(40px);background:radial-gradient(circle at 30% 30%, rgba(0,255,122,0.18), transparent 40%), radial-gradient(circle at 70% 70%, rgba(0,210,122,0.08), transparent 30%)}

        pre{white-space:pre-wrap;font-family:var(--mono);font-size:13px;color:#dfffe9;margin:0}

        @media (max-width:980px){main{grid-template-columns:1fr;padding:16px}}
    </style>
    <script>
        async function postAnalyze(payload){
            const res = await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
            if(!res.ok){const text=await res.text();throw new Error(text||res.statusText)}
            return res.json();
        }

        // Tilt helper
        function bindTilt(el, inner){
            el.addEventListener('mousemove', (e)=>{
                const r = el.getBoundingClientRect();
                const px = (e.clientX - r.left) / r.width - 0.5;
                const py = (e.clientY - r.top) / r.height - 0.5;
                const rotateY = px * 10;
                const rotateX = -py * 10;
                inner.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(8px)`;
            });
            el.addEventListener('mouseleave', ()=>{inner.style.transform='rotateX(0deg) rotateY(0deg) translateZ(0)'});
        }

        document.addEventListener('DOMContentLoaded',()=>{
            const form=document.getElementById('analyze-form');
            const runBtn=document.getElementById('run-btn');
            const reportEl=document.getElementById('report-inner');
            const reportWrap=document.getElementById('report');
            const suspectEl=document.getElementById('suspect');
            const confidenceEl=document.getElementById('confidence');
            const filesEl=document.getElementById('files');
            const candidatesEl=document.getElementById('candidates');

            // tilt bindings
            bindTilt(document.querySelector('.left .card'), document.querySelector('.left .card'));
            bindTilt(reportWrap, reportEl);

            form.addEventListener('submit',async(e)=>{
                e.preventDefault();
                runBtn.disabled=true;const old=runBtn.innerHTML;runBtn.innerHTML='⟳ Running...';
                reportEl.textContent='Running analysis...';
                suspectEl.textContent='-';confidenceEl.textContent='-';filesEl.textContent='-';candidatesEl.textContent='-';
                try{
                    const payload={repo:form.repo.value,good:form.good.value,bad:form.bad.value,test_cmd:form.test_cmd.value,format:'markdown'};
                    const data=await postAnalyze(payload);
                    const suspect=(data.suspect&&data.suspect.sha)||'-';
                    const conf=(data.suspect&&data.suspect.confidence)||'-';
                    const files=(data.suspect&&data.suspect.files_changed&&data.suspect.files_changed.join(', '))||'-';
                    const candidates=(data.candidates||[]).length||0;
                    suspectEl.textContent=suspect;confidenceEl.textContent=conf+'%';filesEl.textContent=files;candidatesEl.textContent=candidates;
                    reportEl.textContent=(data.report||JSON.stringify(data,null,2));
                }catch(err){reportEl.textContent='Error: '+err.message}
                finally{runBtn.disabled=false;runBtn.innerHTML=old}
            });
        });
    </script>
</head>
<body>
    <div class="app">
        <header>
            <div class="logo"><div class="mark">DT</div><div><h1>Debugging Time Machine</h1><div style="font-size:12px;color:var(--muted)">Neon UI — local</div></div></div>
            <div style="font-size:13px;color:var(--muted)">Ready</div>
        </header>
        <main>
            <div class="left">
                <div class="card float">
                    <form id="analyze-form">
                        <div><label>Repository path</label><input name="repo" value="." /></div>
                        <div style="margin-top:12px"><label>Known good commit</label><input name="good" value="HEAD~5" /></div>
                        <div style="margin-top:12px"><label>Known bad commit</label><input name="bad" value="HEAD" /></div>
                        <div style="margin-top:12px"><label>Test command</label><textarea name="test_cmd">python -m pytest</textarea></div>
                        <div style="margin-top:12px;display:flex;gap:10px;align-items:center"><select name="format"><option>Markdown</option><option>JSON</option></select><button id="run-btn" class="btn" type="submit">Run Analysis</button></div>
                    </form>
                </div>
            </div>
            <div class="right">
                <div class="metrics">
                    <div class="metric"><div class="k">Suspect</div><div id="suspect" class="v">-</div></div>
                    <div class="metric"><div class="k">Confidence</div><div id="confidence" class="v">-</div></div>
                    <div class="metric"><div class="k">Files</div><div id="files" class="v">-</div></div>
                    <div class="metric"><div class="k">Candidates</div><div id="candidates" class="v">-</div></div>
                </div>
                <div id="report" class="report">
                    <div class="glow"></div>
                    <div id="report-inner" class="report-inner tilt">Run an analysis to generate a report.</div>
                </div>
            </div>
        </main>
    </div>
</body>
</html>
"""


def _candidate_to_dict(candidate: Any) -> dict[str, Any]:
        if candidate is None:
                return {}
        return {
                "sha": candidate.sha,
                "message": candidate.message,
                "author": candidate.author,
                "is_culprit": candidate.is_culprit,
                "confidence": candidate.confidence,
                "files_changed": list(candidate.files_changed),
                "test_passed": candidate.test_passed,
                "churn": candidate.churn,
        }


def _required(payload: dict[str, Any], key: str) -> str:
        value = str(payload.get(key, "") or "").strip()
        if not value:
                raise ValueError(f"{key} is required")
        return value


class DebuggingTimeMachineHandler(BaseHTTPRequestHandler):
    """HTTP handler for the local UI and analysis API."""

    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        body = APP_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise TypeError("payload must be an object")
            response = analyze_payload(payload)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError, ValueError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
