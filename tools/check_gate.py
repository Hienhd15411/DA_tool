import json, os, requests
URL = os.environ['SUPABASE_URL'].rstrip('/'); KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}
rows = requests.get(f'{URL}/rest/v1/gate_snapshots', headers=H, params={'select': '*', 'order': 'data_date.desc', 'limit': 2}, timeout=60).json()
for r in rows:
    print('GATE', r['data_date'], 'test_start', r['test_start'], 'n_test_days', r['n_test_days'], 'pass', r['strategy_pass'])
    print('CHECKS', json.dumps(r['checks'], ensure_ascii=False))
    print('METRICS', json.dumps(r['metrics'], ensure_ascii=False)[:1500])
