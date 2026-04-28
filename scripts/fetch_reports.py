import warnings; warnings.filterwarnings('ignore')
import sys, os, json

# 切换到 skill 目录
os.chdir(os.path.join(os.path.dirname(__file__), '..', '.agents', 'skills', 'ifind-finance-data'))
sys.path.insert(0, '.')
from call import call

results = {}

# === 泡泡玛特研报 ===
queries_pop = [
    ('pop_2025h1', '泡泡玛特 研报 目标价 业绩预测 评级', '2025-01-01', '2025-06-30'),
    ('pop_2025h2', '泡泡玛特 研报 目标价 业绩预测 评级', '2025-07-01', '2025-12-31'),
    ('pop_2026q1', '泡泡玛特 研报 目标价 业绩预测 评级', '2026-01-01', '2026-04-01'),
]

# === 老铺黄金研报 ===
queries_lao = [
    ('lao_2025h1', '老铺黄金 研报 目标价 业绩预测 评级', '2025-01-01', '2025-06-30'),
    ('lao_2025h2', '老铺黄金 研报 目标价 业绩预测 评级', '2025-07-01', '2025-12-31'),
    ('lao_2026q1', '老铺黄金 研报 目标价 业绩预测 评级', '2026-01-01', '2026-04-01'),
]

all_queries = queries_pop + queries_lao

for key, query, t_start, t_end in all_queries:
    print(f"Fetching: {key} ...", flush=True)
    try:
        r = call('news', 'search_news', {
            'query': query,
            'time_start': t_start,
            'time_end': t_end,
            'size': 10
        })
        results[key] = r
        print(f"  -> ok={r['ok']}, status={r['status_code']}", flush=True)
    except Exception as e:
        results[key] = {'ok': False, 'error': str(e)}
        print(f"  -> Error: {e}", flush=True)

# 写入结果文件
output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'research_reports_raw.json')
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nResults saved to {output_path}", flush=True)
print(f"Total queries: {len(all_queries)}", flush=True)
