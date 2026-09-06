from functools import lru_cache
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .core import ROOT, ADVISORS, Embeddings, Retriever, load_sources, answer_question, synthesize_council

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
        # Reject an oversized request before buffering it, using the
        # declared Content-Length as a first, cheap check.
        declared_length = request.headers.get('content-length')
        if declared_length is not None:
            try:
                if int(declared_length) > 16000:
                    return JSONResponse({'detail':'Request too large.'}, status_code=413)
            except ValueError:
                return JSONResponse({'detail':'Invalid Content-Length.'}, status_code=400)
        # A request with no Content-Length header (or one that understates
        # the real size) isn't caught by the check above -- and
        # `await request.body()` reads the *entire* stream into memory
        # before any size check can run on it, so relying on that alone
        # still buffers an unbounded request before rejecting it. Read the
        # stream directly instead and stop as soon as the limit is
        # exceeded, without ever holding more than ~16KB more than the
        # limit in memory at once. What was read is then stashed on
        # `request._body`, which is exactly the attribute Starlette's own
        # `Request.body()`/`Request.stream()` check first -- so the route
        # handler's later `await request.json()` sees those same bytes
        # rather than an already-exhausted stream or a second read.
        chunks = []
        total = 0
        oversized = False
        async for chunk in request.stream():
            total += len(chunk)
            if total > 16000:
                oversized = True
                break
            chunks.append(chunk)
        if oversized:
            return JSONResponse({'detail':'Request too large.'}, status_code=413)
        request._body = b''.join(chunks)
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
    results=[]
    # Each advisor is isolated: one advisor's model/embedding failure must
    # not discard the other advisors' already-successful, grounded answers
    # in the same council request. A failed advisor gets an explicit 'error'
    # field (never fabricated evidence or an invented answer) so the UI can
    # say what happened instead of silently rendering an empty result that
    # looks identical to "this advisor had nothing relevant to say".
    for advisor in ADVISORS if payload.advisor=='council' else [payload.advisor]:
        try:
            evidence=retriever().search(payload.question,advisor)
            answer=None if payload.retrieval_only else answer_question(payload.question,evidence).model_dump()
            results.append({'advisor':advisor,'answer':answer,'evidence':evidence,'error':None})
        except Exception:
            results.append({'advisor':advisor,'answer':None,'evidence':[],
                             'error':'This advisor could not produce a grounded answer right now.'})
    if not any(r['evidence'] or r['answer'] for r in results):
        # Do not expose model content, filesystem paths or request data in errors.
        raise HTTPException(503,'Cannot produce a grounded answer. Check the local model and embedding setup; no fallback answer was invented.')
    synthesis=synthesize_council(results) if (payload.advisor=='council' and not payload.retrieval_only) else None
    return {'results':results,'duration_ms':round((perf_counter()-started)*1000),
            'mode':'retrieval-only' if payload.retrieval_only else 'local-llm',
            'council_synthesis':synthesis,
            'comparison_note':'Compare the attributed findings below. Differences are not necessarily disagreements; this small corpus may not cover every perspective.'}
