"""研究封存組裝器（archive.py，synthetic-runtime-snapshot-v1）測試。
只用 test_paired_runtime 的合成卡／合成牌表與 stub 引擎（spawn worker 內跑 fake_game，不進 sim2.play_game；真 sim 0 場）。
跨 repo：以固定 argv、shell=False、timeout=60、stdin 傳入記憶體中的合成 archive，唯讀載入主 repo 實際的
js/deck-health-model.js、js/deck-fingerprint.js 與 tests/schema-tools/schema-validator.mjs；不複製網站程式、不落地 archive。"""
import builtins, copy, hashlib, json, os, pathlib, shutil, subprocess, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import archive as ar
import paired
import paired_runtime as rt
import test_paired_runtime as tpr

MAIN_REPO = os.path.join(os.path.dirname(paired.REPO_ROOT), '排球少年')
MAIN_SCHEMA = os.path.join(MAIN_REPO, 'data', 'deck-health', 'schemas', 'research-archive.schema.json')

DECKS = [dict(deck_id='deck-cand', display_name='合成候選', deck=tpr.CAND),
         dict(deck_id='deck-base', display_name='合成基準', deck=tpr.BASE),
         dict(deck_id='deck-opp-x', display_name='合成對手 X', deck=tpr.OPPS[0]['deck']),
         dict(deck_id='deck-opp-y', display_name='合成對手 Y', deck=tpr.OPPS[1]['deck'])]
ROLES = dict(candidate=dict(deck_id='deck-cand'), baseline=dict(deck_id='deck-base'),
             opponents=[dict(opponent_id='opp-x', deck_id='deck-opp-x'), dict(opponent_id='opp-y', deck_id='deck-opp-y')])
META = dict(release_id='synthetic-archive-1', research_version='synthetic-rt-1', conclusion_id='c1', job_id='job-1')


@pytest.fixture(scope='module')
def pkg():
    return tpr.run(workers=2)


@pytest.fixture(scope='module')
def incomplete_pkg():
    return tpr.run(workers=1, game=tpr.fail_cand_b1)


@pytest.fixture(scope='module')
def self_pkg():
    """candidate＝baseline 的自我對照：兩個角色顯式引用同一個 deck_id。"""
    return rt.execute(tpr.U, tpr.CAND, tpr.CAND, tpr.OPPS[:1], tpr.PLAN[:2], experiment_id=tpr.EXP, workers=1,
                      play_game=tpr.fake_game)


def build(p, **kw):
    args = dict(U=tpr.U, decks=copy.deepcopy(DECKS), roles=copy.deepcopy(ROLES), meta=dict(META), evidence=None,
                require_sim2=False)
    args.update(kw)
    return ar.assemble_synthetic_archive(p, **args)


def code_of(fn):
    with pytest.raises(ar.ArchiveAssemblyError) as e:
        fn()
    return e.value.code


def conclusion(a):
    return a['conclusions'][0]


def reseal(p):
    """竄改 identity 後重算 identity_sha256，模擬「自洽但內容被換」的 package。"""
    p['identity_sha256'] = rt._sha(p['identity'])
    return p


# ---- 正常組裝：形狀、哨兵、角色、與 runtime 片段一致 ----

def test_assemble_shape_and_sentinels(pkg):
    before = copy.deepcopy(pkg)
    a = build(pkg)
    assert pkg == before, '組裝不得改動 package'
    assert a['kind'] == 'deck-health-research-archive' and a['schema_version'] == 1
    assert a['data_origin'] == 'synthetic-only' and a['sensitivity'] == 'internal-restricted' and a['do_not_publish'] is True
    assert a['computed_at'] == pkg['execution']['finished_at']
    assert a['engine'] == dict(commit='synthetic:execution-commit-unrecorded',
                               cards_data_hash='synthetic:file-evidence-unavailable', cfg=pkg['identity']['cfg'])
    assert a['cards_data'] == dict(hash='synthetic:file-evidence-unavailable', school_tags_source='synthetic')
    assert [d['deck_id'] for d in a['decks']] == ['deck-cand', 'deck-base', 'deck-opp-x', 'deck-opp-y']
    for d, src in zip(a['decks'], DECKS):
        assert d['cards'] == [[n, c] for n, c in sorted(src['deck'].items())]
        assert d['fingerprint'] == paired.deck_fingerprint(src['deck'])
    c = conclusion(a)
    frag = rt.fragment(pkg, require_sim2=False)
    for k in ('design', 'seeds', 'pairing', 'pair_results', 'pairs'):
        assert c[k] == frag[k], k
    assert c['id'] == 'c1' and c['release_id'] == 'synthetic-archive-1' and c['job_id'] == 'job-1'
    assert c['deck_id'] == 'deck-cand' and c['result_files'] == []
    assert c['baseline_deck'] == dict(deck_id='deck-base', fingerprint=pkg['identity']['decks']['baseline'])
    assert not {'notes', 'flags', 'supersedes'} & set(c)
    pv = a['provenance']
    assert pv['profile'] == 'synthetic-runtime-snapshot-v1' and pv['mode'] == 'synthetic-only' and pv['formal_eligible'] is False
    assert pv['conclusion_id'] == 'c1' and pv['roles'] == ROLES
    assert pv['identity'] == pkg['identity'] and pv['execution'] == pkg['execution']
    assert pv['package'] == dict(kind='internal-run-package', runtime_version='paired-runtime-v1',
                                 identity_sha256=pkg['identity_sha256'], package_sha256=rt._sha(pkg),
                                 fragment_sha256=rt._sha(frag))
    assert pv['run'] == dict(status='complete', usable=True, expected_pairs=6, completed_pairs=6, failure_count=0)
    assert pv['cards']['memory'] == pkg['cards']
    assert pv['cards']['file'] == dict(status='absent', algorithm=None, sha256=None, byte_length=None, label=None, linkage='none')
    assert pv['execution_commit'] == dict(status='absent', value=None)
    assert pv['dirty_scope'] == dict(scope='execution-source-files', status='not-recorded', paths=None)
    assert pv['trust']['overall'] == 'synthetic-unverified'
    # 統計只有一份真相：provenance 不另存 pairs／pair_results
    assert not {'pairs', 'pair_results'} & set(pv) and not {'pairs', 'pair_results'} & set(pv['run'])
    rt._canon(a)   # 可序列化為 canonical JSON（allow_nan=False）
    ar.verify_archive(a, pkg, U=tpr.U, require_sim2=False)


def test_assembler_is_pure_no_disk_git_or_subprocess(pkg, monkeypatch):
    def deny(*a, **k):
        raise AssertionError('組裝器不得讀 disk／呼叫 git／subprocess')
    monkeypatch.setattr(builtins, 'open', deny)
    monkeypatch.setattr(subprocess, 'run', deny)
    monkeypatch.setattr(paired, '_git', deny)
    monkeypatch.setattr(paired, '_read_source', deny)
    a = build(pkg)
    assert a['provenance']['execution_commit']['status'] == 'absent'


def test_roles_may_share_deck_id_for_self_comparison(self_pkg):
    roles = dict(candidate=dict(deck_id='deck-cand'), baseline=dict(deck_id='deck-cand'),
                 opponents=[dict(opponent_id='opp-x', deck_id='deck-opp-x')])
    a = build(self_pkg, decks=[copy.deepcopy(DECKS[0]), copy.deepcopy(DECKS[2])], roles=roles)
    assert conclusion(a)['baseline_deck']['deck_id'] == 'deck-cand'
    assert all(p['delta'] == 0 for p in conclusion(a)['pairs'])


# ---- caller assertion：commit、dirty scope 只記在 provenance ----

def test_caller_commit_is_only_recorded_as_assertion(pkg):
    sha = 'ab' * 20
    a = build(pkg, evidence=dict(execution_commit=sha))
    assert a['engine']['commit'] == 'synthetic:execution-commit-unrecorded'
    assert a['provenance']['execution_commit'] == dict(status='caller-asserted', value=sha)
    assert json.dumps(a).count(sha) == 1
    assert code_of(lambda: build(pkg, evidence=dict(execution_commit='HEAD'))) == 'bad_evidence'


def test_dirty_scope_only_execution_sources(pkg):
    a = build(pkg, evidence=dict(source_status={'deck_health/sim2.py': 'M'}))
    assert a['provenance']['dirty_scope'] == dict(scope='execution-source-files', status='caller-asserted',
                                                  paths={'deck_health/sim2.py': 'M'})
    assert code_of(lambda: build(pkg, evidence=dict(source_status={'data/private.json': 'M'}))) == 'bad_evidence'
    assert code_of(lambda: build(pkg, evidence=dict(unknown=1))) == 'bad_evidence'


# ---- 卡庫 bytes：組裝器自算 SHA-256；不拿 U 記憶體 hash 冒充 ----

def test_cards_bytes_synthetic_json_linkage(pkg):
    b = json.dumps(tpr.U, ensure_ascii=False).encode('utf-8')
    a = build(pkg, evidence=dict(cards_file=dict(label='synthetic-cards.json', bytes=b, derivation='synthetic-json-utf8')))
    h = hashlib.sha256(b).hexdigest()
    assert a['cards_data']['hash'] == a['engine']['cards_data_hash'] == 'sha256:' + h
    assert h not in (pkg['cards']['input']['sha256'], pkg['cards']['used']['sha256'])
    assert a['provenance']['cards']['file'] == dict(status='caller-bytes', algorithm='sha256-of-caller-bytes', sha256=h,
                                                    byte_length=len(b), label='synthetic-cards.json',
                                                    linkage='synthetic-json-equals-U')


def test_cards_bytes_unlinked_and_rejections(pkg):
    a = build(pkg, evidence=dict(cards_file=dict(label='cards_data.js', bytes=b'synthetic bytes')))
    assert a['provenance']['cards']['file']['linkage'] == 'unlinked'
    assert a['cards_data']['hash'] == 'sha256:' + hashlib.sha256(b'synthetic bytes').hexdigest()
    other = copy.deepcopy(tpr.U); other[tpr.UNUSED]['srv'] += 1
    wrong = json.dumps(other).encode('utf-8')
    assert code_of(lambda: build(pkg, evidence=dict(cards_file=dict(label='x.json', bytes=wrong,
                                                                     derivation='synthetic-json-utf8')))) == 'cards_file_unlinked'
    assert code_of(lambda: build(pkg, evidence=dict(cards_file=dict(label='x.json', bytes='ab' * 32)))) == 'hex_without_bytes'
    assert code_of(lambda: build(pkg, evidence=dict(cards_file=dict(label='C:/x/cards.json', bytes=b'x')))) == 'bad_evidence'


# ---- package 拒收 ----

def test_rejects_incomplete_package(incomplete_pkg):
    assert incomplete_pkg['run']['status'] == 'incomplete'
    assert code_of(lambda: build(incomplete_pkg)) == 'incomplete'


def test_rejects_identity_cfg_and_seed_plan_tampering(pkg):
    p = copy.deepcopy(pkg); p['identity']['experiment_id'] = 'other'
    assert code_of(lambda: build(p)) == 'identity_hash'
    p = copy.deepcopy(pkg); p['identity']['cfg']['__tamper__'] = 1; reseal(p)
    assert code_of(lambda: build(p)) == 'cfg_hash'
    p = copy.deepcopy(pkg); p['identity']['experiment_id'] = 'other'; reseal(p)
    assert code_of(lambda: build(p)) == 'seed_plan'


def test_rejects_stub_engine_when_sim2_required_and_bad_outcomes(pkg):
    assert code_of(lambda: build(pkg, require_sim2=True)) == 'contract'
    for side in (dict(outcome='draw', metric_value=0), dict(outcome='win', metric_value=0.5)):
        p = copy.deepcopy(pkg); p['run']['pair_results'][0]['candidate'] = side
        assert code_of(lambda: build(p)) == 'contract'


def test_rejects_execution_and_version_inconsistency(pkg):
    for k, v in (('hash_probe_consistent', False), ('worker_priorities', [0x20]), ('submit_error', 'X')):
        p = copy.deepcopy(pkg); p['execution'][k] = v
        assert code_of(lambda: build(p)) == 'execution_inconsistent', k
    p = copy.deepcopy(pkg); p['not_delivered'] = []
    assert code_of(lambda: build(p)) == 'mixed_version'


def test_rejects_cards_memory_mismatch(pkg):
    u = copy.deepcopy(tpr.U); u['SYN-RT-001']['srv'] += 1
    assert code_of(lambda: build(pkg, U=u)) == 'cards_memory_mismatch'
    u = copy.deepcopy(tpr.U); u[tpr.UNUSED]['srv'] += 1   # 未用卡也屬於 input hash
    assert code_of(lambda: build(pkg, U=u)) == 'cards_memory_mismatch'


# ---- 牌表／角色拒收 ----

def test_rejects_deck_and_role_tampering(pkg):
    decks = copy.deepcopy(DECKS); decks[1]['deck'] = tpr.deck(*range(1, 9), 11, 12)
    assert code_of(lambda: build(pkg, decks=decks)) == 'deck_tampered'
    roles = copy.deepcopy(ROLES); roles['opponents'][0]['deck_id'], roles['opponents'][1]['deck_id'] = 'deck-opp-y', 'deck-opp-x'
    assert code_of(lambda: build(pkg, roles=roles)) == 'deck_tampered'
    roles = copy.deepcopy(ROLES); roles['opponents'].pop()
    assert code_of(lambda: build(pkg, roles=roles)) == 'role_mismatch'
    roles = copy.deepcopy(ROLES); roles['baseline']['deck_id'] = 'ghost'
    assert code_of(lambda: build(pkg, roles=roles)) == 'role_mismatch'
    decks = copy.deepcopy(DECKS) + [dict(deck_id='deck-cand', display_name='重複', deck=tpr.BASE)]
    assert code_of(lambda: build(pkg, decks=decks)) == 'bad_decks'
    decks = copy.deepcopy(DECKS) + [dict(deck_id='deck-extra', display_name='未引用', deck=tpr.BASE)]
    assert code_of(lambda: build(pkg, decks=decks)) == 'bad_decks'
    decks = copy.deepcopy(DECKS); decks[0]['deck'] = dict(decks[0]['deck'], **{'SYN-RT-001': 3})
    assert code_of(lambda: build(pkg, decks=decks)) == 'bad_decks'   # 39 張


def test_rejects_meta_extras_and_non_synthetic_ids(pkg):
    assert code_of(lambda: build(pkg, meta=dict(META, notes='x'))) == 'bad_meta'
    assert code_of(lambda: build(pkg, meta=dict(META, cfg={}))) == 'bad_meta'
    assert code_of(lambda: build(pkg, meta=dict(META, release_id='rt-1'))) == 'not_synthetic'
    assert code_of(lambda: build(pkg, meta=dict(META, research_version='v1'))) == 'not_synthetic'


# ---- 完整入口重驗與 formal 閘門 ----

def test_verify_archive_detects_tampering(pkg):
    a = build(pkg)
    cases = [
        (lambda x: conclusion(x)['pairs'][0].__setitem__('delta', 0.25), 'conclusion_mismatch'),
        (lambda x: conclusion(x)['pair_results'][0]['candidate'].__setitem__('outcome', 'loss'), 'conclusion_mismatch'),
        (lambda x: x['provenance']['identity'].__setitem__('experiment_id', 'x'), 'provenance_mismatch'),
        (lambda x: x['provenance']['execution_commit'].update(status='verified', value='cd' * 20), 'provenance_mismatch'),
        (lambda x: x['provenance']['cards']['file'].__setitem__('linkage', 'synthetic-json-equals-U'), 'provenance_mismatch'),
        (lambda x: x['provenance']['execution'].__setitem__('games_played', 0), 'provenance_mismatch'),
        (lambda x: x['engine'].__setitem__('commit', 'ab' * 20), 'archive_mismatch'),
        (lambda x: x.__setitem__('data_origin', 'research'), 'archive_mismatch'),
        (lambda x: x['decks'][1]['cards'][0].__setitem__(1, 3), 'deck_tampered'),
        (lambda x: x['provenance']['roles']['candidate'].__setitem__('deck_id', 'deck-base'), 'deck_tampered'),
    ]
    for mutate, want in cases:
        b = copy.deepcopy(a); mutate(b)
        assert code_of(lambda: ar.verify_archive(b, pkg, U=tpr.U, require_sim2=False)) == want, want


def test_formal_ready_always_rejects_synthetic_profile(pkg):
    a = build(pkg)
    assert code_of(lambda: ar.assert_formal_ready(a)) == 'synthetic_profile_not_formal'
    b = copy.deepcopy(a); b['data_origin'] = 'research'
    assert code_of(lambda: ar.assert_formal_ready(b)) == 'synthetic_profile_not_formal'
    assert code_of(lambda: ar.assert_formal_ready({})) == 'formal_not_delivered'


def test_main_repo_schema_mirrors_runtime_constants():
    with open(MAIN_SCHEMA, encoding='utf-8') as f:
        s = json.load(f)
    d = s['$defs']
    assert d['provenance']['properties']['profile']['const'] == ar.PROFILE
    assert d['provenanceIdentity']['properties']['manual_env']['required'] == list(rt.MANUAL_ENV_KEYS_FULL)
    assert set(d['provenanceIdentity']['required']) == set(build_identity_keys())
    assert set(d['provenanceExecution']['required']) == set(EXECUTION_KEYS)


def build_identity_keys():
    return rt.identity_for(tpr.U, tpr.CAND, tpr.BASE, tpr.OPPS, tpr.PLAN, experiment_id=tpr.EXP, play_game=tpr.fake_game).keys()


EXECUTION_KEYS = ('start_method', 'workers_requested', 'workers_effective', 'worker_pids', 'worker_priorities', 'hash_seed',
                  'hash_probe_consistent', 'schedule', 'submitted_tasks', 'submit_error', 'task_workers', 'tasks_by_worker',
                  'games_played', 'started_at', 'finished_at', 'python_flags')


def test_execution_keys_match_package(pkg):
    assert set(pkg['execution']) == set(EXECUTION_KEYS)


# ---- 跨 repo：主 repo 實際 JS model／指紋／Ajv（固定 argv、shell=False、timeout=60、stdin）----

NODE_SCRIPT = (
    "const [modelUrl, schemaUrl, fpUrl] = process.argv.slice(-3);\n"
    "const { validateResearchArchive, verifyFingerprints } = await import(modelUrl);\n"
    "const { validateWithJsonSchema } = await import(schemaUrl);\n"
    "const { deckFingerprint } = await import(fpUrl);\n"
    "let s = ''; process.stdin.setEncoding('utf8');\n"
    "for await (const c of process.stdin) s += c;\n"
    "const input = JSON.parse(s);\n"
    "const cases = {};\n"
    "for (const [name, a] of Object.entries(input.cases || {})) {\n"
    "  const sync = validateResearchArchive(a);\n"
    "  const fp = await verifyFingerprints(a, cards => deckFingerprint(new Map(cards)), { path: 'archive' });\n"
    "  const aj = validateWithJsonSchema('archive', a);\n"
    "  cases[name] = { sync: { ok: sync.ok, codes: sync.errors.map(e => e.code) },\n"
    "    fp: { ok: fp.ok, codes: fp.errors.map(e => e.code) },\n"
    "    ajv: { valid: aj.valid, errors: aj.errors.map(e => `${e.instancePath} ${e.keyword} ${e.message}`) } };\n"
    "}\n"
    "const vectors = [];\n"
    "for (const v of input.vectors || []) vectors.push(await deckFingerprint(new Map(v)));\n"
    "process.stdout.write(JSON.stringify({ cases, vectors }));\n")


def node_check(cases=None, vectors=None):
    node = shutil.which('node')
    assert node, '找不到 node'
    paths = [pathlib.Path(MAIN_REPO, *p) for p in
             (('js', 'deck-health-model.js'), ('tests', 'schema-tools', 'schema-validator.mjs'), ('js', 'deck-fingerprint.js'))]
    for p in paths:
        assert p.is_file(), p
    urls = [p.as_uri() for p in paths]
    payload = json.dumps(dict(cases=cases or {}, vectors=vectors or []), ensure_ascii=False)
    p = subprocess.run([node, '--input-type=module', '-e', NODE_SCRIPT] + urls, input=payload, capture_output=True,
                       text=True, encoding='utf-8', timeout=60, shell=False, cwd=HERE)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert set(out) == {'cases', 'vectors'} and set(out['cases']) == set(cases or {})
    return out


def test_node_main_repo_accepts_assembled_and_rejects_tampering(pkg):
    a = build(pkg, evidence=dict(execution_commit='ab' * 20, source_status={'deck_health/sim2.py': 'M'},
                                 cards_file=dict(label='synthetic-cards.json', bytes=json.dumps(tpr.U).encode('utf-8'),
                                                 derivation='synthetic-json-utf8')))

    def mut(f):
        b = copy.deepcopy(a); f(b); return b

    def pc(b):
        return conclusion(b)

    cases = {
        'ok': a,
        'ok_minimal': build(pkg),
        'baseline_cards_swapped': mut(lambda b: b['decks'][1]['cards'].__setitem__(0, ['SYN-RT-012', 4])),
        'baseline_fp': mut(lambda b: pc(b)['baseline_deck'].__setitem__('fingerprint', 'a' * 40)),
        'no_provenance': mut(lambda b: b.pop('provenance')),
        'research_origin': mut(lambda b: b.__setitem__('data_origin', 'research')),
        'role_wrong_deck': mut(lambda b: b['provenance']['roles']['opponents'][0].__setitem__('deck_id', 'deck-base')),
        'role_dangling': mut(lambda b: b['provenance']['roles']['opponents'][0].__setitem__('deck_id', 'ghost')),
        'delta': mut(lambda b: pc(b)['pairs'][0].__setitem__('delta', pc(b)['pairs'][0]['delta'] + 0.25)),
        'draw': mut(lambda b: pc(b)['pair_results'][0]['candidate'].update(outcome='draw', metric_value=0)),
        'prov_extra': mut(lambda b: b['provenance'].__setitem__('notes', 'x')),
        'formal_true': mut(lambda b: b['provenance'].__setitem__('formal_eligible', True)),
        'file_linkage_without_bytes': mut(lambda b: b['provenance']['cards']['file'].update(
            status='absent', algorithm=None, sha256=None, byte_length=None, label=None, linkage='synthetic-json-equals-U')),
        'commit_without_value': mut(lambda b: b['provenance']['execution_commit'].__setitem__('value', None)),
        'cfg_drift': mut(lambda b: b['engine']['cfg'].__setitem__('__tamper__', 1)),
        'seeds_drift': mut(lambda b: b['provenance']['identity']['plan'][0].__setitem__('seed', 7)),
        'priority': mut(lambda b: b['provenance']['execution'].__setitem__('worker_priorities', [0x20])),
    }
    out = node_check(cases)['cases']
    for name in ('ok', 'ok_minimal'):
        assert out[name] == dict(sync=dict(ok=True, codes=[]), fp=dict(ok=True, codes=[]), ajv=dict(valid=True, errors=[])), \
            (name, out[name])
    want = {
        'baseline_fp': 'baseline_mismatch', 'no_provenance': 'missing_field', 'research_origin': 'provenance_untrusted',
        'role_wrong_deck': 'provenance_mismatch', 'role_dangling': 'dangling_ref', 'delta': 'delta_mismatch',
        'draw': 'draw_rejected', 'prov_extra': 'unknown_field', 'formal_true': 'bad_provenance',
        'file_linkage_without_bytes': 'bad_provenance', 'commit_without_value': 'bad_provenance',
        'cfg_drift': 'provenance_mismatch', 'seeds_drift': 'provenance_mismatch', 'priority': 'bad_provenance',
    }
    for name, code in want.items():
        assert out[name]['sync']['ok'] is False and code in out[name]['sync']['codes'], (name, out[name])
    # 牌表換卡但宣告指紋不變：同步驗證看不出，async verifyFingerprints 重算 SHA-1 才抓到
    sw = out['baseline_cards_swapped']
    assert sw['sync']['ok'] is True and sw['fp'] == dict(ok=False, codes=['fingerprint_mismatch'])
    # JSON Schema（test-only Ajv）可表達的結構約束
    for name in ('no_provenance', 'research_origin', 'prov_extra', 'formal_true', 'file_linkage_without_bytes',
                 'commit_without_value', 'priority', 'draw'):
        assert out[name]['ajv']['valid'] is False, name
