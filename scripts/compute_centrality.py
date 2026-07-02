"""
compute_centrality.py
NexaCore Blast Radius Project — pre-computation script.
Writes:
  data/centrality_scores.csv  — betweenness, PageRank, eigenvector for all 90 nodes
  data/blast_radius.csv       — broken reachable pairs per node (all nodes with blast > 0)

Run from project root: python3 scripts/compute_centrality.py
"""
import csv, math
from collections import defaultdict, deque

random_seed = 42  # topology is deterministic; seed documented for reproducibility

nodes_raw = list(csv.DictReader(open('data/nodes.csv')))
edges_raw = list(csv.DictReader(open('data/edges.csv')))

node_ids = [n['id'] for n in nodes_raw]
node_idx = {nid: i for i, nid in enumerate(node_ids)}
N = len(node_ids)

out_adj = defaultdict(list)
in_adj  = defaultdict(list)
for e in edges_raw:
    i, j = node_idx[e['from']], node_idx[e['to']]
    out_adj[i].append(j)
    in_adj[j].append(i)

# =============================================================================
# 1. Betweenness centrality (Brandes, directed, normalized)
# =============================================================================
def betweenness_centrality():
    bc = [0.0] * N
    for s in range(N):
        stack, pred   = [], [[] for _ in range(N)]
        sigma         = [0] * N;  sigma[s] = 1
        dist          = [-1] * N; dist[s]  = 0
        queue         = deque([s])
        while queue:
            v = queue.popleft(); stack.append(v)
            for w in out_adj[v]:
                if dist[w] < 0:
                    queue.append(w); dist[w] = dist[v] + 1
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]; pred[w].append(v)
        delta = [0.0] * N
        while stack:
            w = stack.pop()
            for v in pred[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    norm = (N - 1) * (N - 2)
    return [b / norm if norm > 0 else 0 for b in bc]

# =============================================================================
# 2. PageRank (alpha=0.85, convergence-based)
# =============================================================================
def pagerank(alpha=0.85, max_iter=100, tol=1e-8):
    pr = [1.0 / N] * N
    for _ in range(max_iter):
        pr_new = [(1 - alpha) / N] * N
        for v in range(N):
            out_v = out_adj[v]
            if out_v:
                share = pr[v] / len(out_v)
                for w in out_v:
                    pr_new[w] += alpha * share
            else:
                for w in range(N):
                    pr_new[w] += alpha * pr[v] / N
        if sum(abs(pr_new[i] - pr[i]) for i in range(N)) < tol:
            pr = pr_new; break
        pr = pr_new
    return pr

# =============================================================================
# 3. Eigenvector centrality (power iteration, in-adjacency)
# =============================================================================
def eigenvector_centrality(max_iter=200, tol=1e-8):
    ec = [1.0 / N] * N
    for _ in range(max_iter):
        ec_new = [sum(ec[u] for u in in_adj[v]) for v in range(N)]
        norm   = math.sqrt(sum(x**2 for x in ec_new)) or 1.0
        ec_new = [x / norm for x in ec_new]
        if sum(abs(ec_new[i] - ec[i]) for i in range(N)) < tol:
            ec = ec_new; break
        ec = ec_new
    return ec

# =============================================================================
# 4. Blast radius (broken reachable pairs)
# For each node X: count of (source, target) pairs in the baseline
# reachable-pairs set that are no longer reachable after X is removed.
# This correctly captures both upstream and downstream impact,
# and works for external leaf nodes (kyc-vendor etc.) as well as hubs.
# =============================================================================
def build_baseline_pairs():
    pairs = set()
    for s in range(N):
        visited = set(); queue = deque([s])
        while queue:
            v = queue.popleft()
            if v in visited: continue
            visited.add(v)
            for w in out_adj[v]:
                if w not in visited: queue.append(w)
        for t in visited:
            if t != s: pairs.add((s, t))
    return pairs

def can_reach_without(frm, tgt, excluded):
    if frm == excluded or tgt == excluded: return False
    visited = set(); queue = deque([frm])
    while queue:
        v = queue.popleft()
        if v == tgt: return True
        if v in visited: continue
        visited.add(v)
        for w in out_adj[v]:
            if w != excluded and w not in visited: queue.append(w)
    return False

print("Betweenness centrality...")
bc = betweenness_centrality()
print("PageRank...")
pr = pagerank()
print("Eigenvector centrality...")
ec = eigenvector_centrality()
print("Building baseline reachable pairs...")
baseline_pairs = build_baseline_pairs()
print(f"  Baseline pairs: {len(baseline_pairs)}")
print("Blast radius simulation...")
blast = []
for x in range(N):
    broken = sum(
        1 for (s, t) in baseline_pairs
        if s == x or t == x or not can_reach_without(s, t, x)
    )
    blast.append(broken)
print("Done.")

# =============================================================================
# 5. Normalize and write centrality_scores.csv
# =============================================================================
def normalize(vals):
    mn, mx = min(vals), max(vals)
    return [(v - mn) / (mx - mn) if mx > mn else 0.0 for v in vals]

bc_n = normalize(bc); pr_n = normalize(pr); ec_n = normalize(ec)
blast_n = normalize(blast)
composite = [(bc_n[i] + pr_n[i] + ec_n[i]) / 3 for i in range(N)]
node_meta = {n['id']: n for n in nodes_raw}

centrality_rows = []
for i, nid in enumerate(node_ids):
    n = node_meta[nid]
    centrality_rows.append({
        'node_id':          nid,
        'name':             n['name'],
        'tier':             n['tier'],
        'revenue_weight':   int(n['revenue_weight']),
        'risk_node':        n['risk_node'],
        'betweenness_raw':  round(bc[i], 6),
        'betweenness_norm': round(bc_n[i], 4),
        'pagerank_raw':     round(pr[i], 6),
        'pagerank_norm':    round(pr_n[i], 4),
        'eigenvector_raw':  round(ec[i], 6),
        'eigenvector_norm': round(ec_n[i], 4),
        'composite_score':  round(composite[i], 4),
        'blast_radius':     blast[i],
        'blast_norm':       round(blast_n[i], 4),
    })

centrality_rows.sort(key=lambda r: -r['composite_score'])

fields_c = ['node_id','name','tier','revenue_weight','risk_node',
            'betweenness_raw','betweenness_norm',
            'pagerank_raw','pagerank_norm',
            'eigenvector_raw','eigenvector_norm',
            'composite_score','blast_radius','blast_norm']

with open('data/centrality_scores.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields_c)
    w.writeheader(); w.writerows(centrality_rows)

# =============================================================================
# 6. Write blast_radius.csv (all nodes with blast > 0, sorted desc)
# =============================================================================
blast_rows = sorted(
    [{'node_id':        node_ids[i],
      'name':           node_meta[node_ids[i]]['name'],
      'tier':           node_meta[node_ids[i]]['tier'],
      'blast_radius':   blast[i],
      'blast_norm':     round(blast_n[i], 4),
      'betweenness_norm': round(bc_n[i], 4),
      'pagerank_norm':    round(pr_n[i], 4),
      'eigenvector_norm': round(ec_n[i], 4),
      'composite_score':  round(composite[i], 4),
      'risk_node':      node_meta[node_ids[i]]['risk_node'],
      'revenue_weight': int(node_meta[node_ids[i]]['revenue_weight']),
      'spof':           node_meta[node_ids[i]]['spof'],
    } for i in range(N) if blast[i] > 0],
    key=lambda r: -r['blast_radius']
)

fields_b = ['node_id','name','tier','blast_radius','blast_norm',
            'betweenness_norm','pagerank_norm','eigenvector_norm',
            'composite_score','risk_node','revenue_weight','spof']

with open('data/blast_radius.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields_b)
    w.writeheader(); w.writerows(blast_rows)

# =============================================================================
# 7. Console summary
# =============================================================================
print(f"\n{'Node':<25} {'BW':>6} {'PR':>6} {'EV':>6} {'Comp':>6} {'Blast':>6}")
print("-"*60)
for r in centrality_rows[:15]:
    flag = " *" if r['risk_node']=='True' else ""
    print(f"  {r['node_id']:<23} {r['betweenness_norm']:>6.3f} {r['pagerank_norm']:>6.3f} "
          f"{r['eigenvector_norm']:>6.3f} {r['composite_score']:>6.3f} {r['blast_radius']:>6}{flag}")
print()
kyc = next(r for r in centrality_rows if r['node_id']=='kyc-vendor')
br_rank = sorted(range(N), key=lambda i: -blast[i]).index(node_idx['kyc-vendor']) + 1
print(f"kyc-vendor: composite={kyc['composite_score']}, blast={kyc['blast_radius']}, blast_rank={br_rank}/90")
print(f"\nFiles written: data/centrality_scores.csv, data/blast_radius.csv")
