import pytest

from brain.core import Answer, chunks, load_sources, validate_answer, answer_question, synthesize_council
from brain.evaluate import evaluate, gate, questions_fingerprint


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


def test_gate_rejects_a_swapped_question_set_of_the_same_size():
    # Same case count alone used to be accepted as "no benchmark change",
    # so replacing the questions with an easier set of the same size would
    # silently pass. The gate must also check question identity.
    cases_a=[{'id':'n1','query':'Original question?','advisor':'naval','split':'dev','expected':['naval-x']}]
    cases_b=[{'id':'n1','query':'A much easier question?','advisor':'naval','split':'dev','expected':['naval-x']}]
    good={'cases':1,'advisor_isolation':True,'mrr':1.0,'recall_at_3':1.0,
          'questions_sha256':questions_fingerprint(cases_a)}
    same_questions={**good,'questions_sha256':questions_fingerprint(cases_a)}
    swapped_questions={**good,'questions_sha256':questions_fingerprint(cases_b)}
    assert gate(same_questions,good)
    assert not gate(swapped_questions,good)


def test_api_rejects_invalid_advisor_and_foreign_origin():
    from fastapi.testclient import TestClient
    from brain.api import app
    client=TestClient(app)
    assert client.post('/api/query',json={'question':'Example question','advisor':'unknown'}).status_code==422
    assert client.get('/api/sources',headers={'Origin':'https://example.com'}).status_code==403


def test_one_advisor_failure_does_not_discard_the_others_and_is_reported():
    # README previously claimed test coverage for per-advisor failure
    # isolation that didn't actually exist. This exercises the real
    # /api/query endpoint with one advisor's retrieval forced to raise,
    # confirming the other two still return their real evidence and the
    # failed one gets an explicit, non-empty error instead of a result
    # that's silently indistinguishable from "nothing relevant found".
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    import brain.api as api_module
    from brain.api import app

    class FlakyRetriever:
        def search(self, question, advisor):
            if advisor == 'hormozi':
                raise RuntimeError('simulated retrieval failure')
            return [{'chunk_id': f'{advisor}-1', 'source_id': f'{advisor}-1', 'advisor_id': advisor,
                     'title': 'Title', 'url': 'https://example.com', 'text': 'Evidence text.',
                     'attribution': 'Attribution.'}]

    with patch.object(api_module, 'retriever', return_value=FlakyRetriever()):
        client = TestClient(app)
        response = client.post('/api/query', json={
            'question': 'Example question about growth?', 'advisor': 'council', 'retrieval_only': True,
        })

    assert response.status_code == 200
    results = {r['advisor']: r for r in response.json()['results']}
    assert results['hormozi']['error'], 'the failed advisor must carry a non-empty error'
    assert results['hormozi']['evidence'] == [], 'a failure must never fabricate evidence'
    assert results['hormozi']['answer'] is None
    for advisor in ('naval', 'kallaway'):
        assert results[advisor]['error'] is None
        assert results[advisor]['evidence'], f'{advisor} must keep its real evidence despite the other failure'



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
    assert synthesis['shared_topics'], 'shared vocabulary (effort/value) should surface as a shared topic'
    original_citations={'hormozi-1','naval-1'}
    for group in (synthesis['shared_topics'], synthesis['distinct_perspectives']):
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
    assert not synthesis['shared_topics']
    assert synthesis['distinct_perspectives']


def test_council_synthesis_never_claims_semantic_agreement_even_on_high_overlap():
    # A negation-based check used to try to keep contradicting claims out of
    # the old "agreements" bucket. That approach doesn't hold up: a regex
    # for "n't" can't match inside a contraction like "doesn't" (no word
    # boundary sits between "sn" and "'t"), and a pure antonym pair like
    # "improves" vs. "harms" carries no negation word for any regex to find
    # in the first place -- there is no reliable keyword-based way to tell
    # agreement from disagreement. So neither bucket claims agreement at
    # all any more; both must expose the full claim text so a human reader
    # can judge for themselves, for a contraction-negated pair and a
    # pure-antonym pair alike.
    negated_pair=[
        {'advisor':'hormozi','answer':{'status':'answered','claims':[
            {'text':'Increasing prices improves customer retention.','citations':['hormozi-3']}]}},
        {'advisor':'naval','answer':{'status':'answered','claims':[
            {'text':"Increasing prices doesn't improve customer retention.",'citations':['naval-2']}]}},
    ]
    antonym_pair=[
        {'advisor':'hormozi','answer':{'status':'answered','claims':[
            {'text':'Increasing prices improves customer retention.','citations':['hormozi-3']}]}},
        {'advisor':'naval','answer':{'status':'answered','claims':[
            {'text':'Increasing prices harms customer retention.','citations':['naval-2']}]}},
    ]
    for results in (negated_pair, antonym_pair):
        synthesis=synthesize_council(results)
        all_pairs=synthesis['shared_topics']+synthesis['distinct_perspectives']
        assert len(all_pairs)==1, 'the one cross-advisor claim pair must land in exactly one bucket'
        pair=all_pairs[0]
        assert pair['claims'][0]['text'] and pair['claims'][1]['text'], \
            'full claim text must always be present so a reader can judge agreement themselves'
    note=synthesize_council(negated_pair)['note'].lower()
    assert 'semantic' in note and 'agreement' in note, 'note must caveat that grouping is not a semantic judgement'

