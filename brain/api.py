from functools import lru_cache
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .core import ROOT, ADVISORS, Embeddings, Retriever, load_sources, answer_question

app = FastAPI(title="Creator Brain", docs_url="/docs")


@app.middleware('http')
async def local_only(request: Request, call_next):
    host = request.headers.get('host', '')
    if host.split(':')[0] not in ('127.0.0.1', 'localhost', 'testserver'):
        return JSONResponse({'detail':'Local access only.'}, status_code=403)
    origin = request.headers.get('origin')
    if origin and origin != f'http://{host}':
        return JSONResponse({'detail':'Cross-origin requests refused.'}, status_code=403)
    if request.method == 'POST':
        body = await request.body()
        if len(body) > 16000:
            return JSONResponse({'detail':'Request too large.'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    return response


@lru_cache(maxsize=1)
def retriever():
    return Retriever(load_sources(), Embeddings())


class Query(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    advisor: Literal['hormozi','naval','kallaway','council'] = 'council'
    retrieval_only: bool = False


@app.get('/')
def home():
    return FileResponse(ROOT/'web/index.html')


@app.get('/app.js')
def javascript():
    return FileResponse(ROOT/'web/app.js', media_type='text/javascript')


@app.get('/style.css')
def stylesheet():
    return FileResponse(ROOT/'web/style.css', media_type='text/css')


@app.get('/api/sources')
def sources():
    return [s.model_dump() for s in load_sources()]


@app.post('/api/query')
def query(payload: Query):
    started=perf_counter()
    try:
        results=[]
        for advisor in ADVISORS if payload.advisor=='council' else [payload.advisor]:
            evidence=retriever().search(payload.question,advisor)
            answer=None if payload.retrieval_only else answer_question(payload.question,evidence).model_dump()
            results.append({'advisor':advisor,'answer':answer,'evidence':evidence})
        return {'results':results,'duration_ms':round((perf_counter()-started)*1000),
                'mode':'retrieval-only' if payload.retrieval_only else 'local-llm',
                'comparison_note':'Compare the attributed findings below. Differences are not necessarily disagreements; this small corpus may not cover every perspective.'}
    except Exception as e:
        # Do not expose model content, filesystem paths or request data in errors.
        raise HTTPException(503,'Cannot produce a grounded answer. Check the local model and embedding setup; no fallback answer was invented.') from e
