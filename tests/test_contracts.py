import pytest

from brain.core import Answer, chunks, load_sources, validate_answer, answer_question, synthesize_council
from brain.evaluate import evaluate, gate


def test_chunk_ids_are_stable_and_content_sensitive():
    sources=load_sources()
    first=chunks(sources)
    assert first==chunks(sources)
    sources[0].text='An additional original note. '+sources[0].text  # prepend: guaranteed to fall inside chunk 0's window regardless of source length
    assert chunks(sources)[0]['chunk_id']!=first[0]['chunk_id']


def test_foreign_citation_is_rejected():
    evidence=[{'chunk_id':'naval-1'}]
    with pytest.raises(ValueError):
        validate_answer({'status':'answered','claims':[{'text':'Claim','citations':['hormozi-1']}]},evidence)
    assert validate_answer({'status':'answered','claims':[{'text':'Claim','citations':['naval-1']}]},evidence).status=='answered'


def test_abstention_cannot_smuggle_claims():
    with pytest.raises(ValueError):
        validate_answer({'status':'insufficient_evidence','claims':[{'text':'Claim','citations':['x']}]},[{'chunk_id':'x'}])
    assert answer_question('Unknown question',[]).status=='insufficient_evidence'


def test_gate_rejects_regression_and_empty_cases():
    good={'cases':9,'advisor_isolation':True,'mrr':1.0,'recall_at_3':1.0}
    assert gate(good,good)
    assert not gate({**good,'mrr':0.8},good)
    assert not gate({**good,'advisor_isolation':False},good)
    assert not gate({**good,'cases':0},good)
    with pytest.raises(ValueError):evaluate(None,[])


def test_api_rejects_invalid_advisor_and_foreign_origin():
    from fastapi.testclient import TestClient
    from brain.api import app
    client=TestClient(app)
    assert client.post('/api/query',json={'question':'Example question','advisor':'unknown'}).status_code==422
    assert client.get('/api/sources',headers={'Origin':'https://example.com'}).status_code==403


def test_council_synthesis_flags_shared_terms_without_inventing_content():
    results=[
        {'advisor':'hormozi','answer':{'status':'answered','claims':[
            {'text':'Lowering perceived effort increases offer value.','citations':['hormozi-1']}]}},
        {'advisor':'naval','answer':{'status':'answered','claims':[
            {'text':'Reducing effort and increasing leverage compounds value over time.','citations':['naval-1']}]}},
        {'advisor':'kallaway','answer':{'status':'insufficient_evidence','claims':[]}},
    ]
    synthesis=synthesize_council(results)
    assert synthesis['advisors_answered']==['hormozi','naval']
    assert synthesis['advisors_abstained']==['kallaway']
    assert synthesis['agreements'], 'shared vocabulary (effort/value) should surface as agreement'
    original_citations={'hormozi-1','naval-1'}
    for group in (synthesis['agreements'], synthesis['distinct_perspectives']):
        for pair in group:
            for claim in pair['claims']:
                assert set(claim['citations'])<=original_citations


def test_council_synthesis_without_shared_vocabulary_is_a_distinct_perspective():
    results=[
        {'advisor':'hormozi','answer':{'status':'answered','claims':[
            {'text':'Bonuses should remove friction from the outcome.','citations':['hormozi-2']}]}},
        {'advisor':'kallaway','answer':{'status':'answered','claims':[
            {'text':'Hooks rely on studying audience psychology.','citations':['kallaway-1']}]}},
    ]
    synthesis=synthesize_council(results)
    assert not synthesis['agreements']
    assert synthesis['distinct_perspectives']
