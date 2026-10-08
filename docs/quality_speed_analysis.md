# Phase 03 quality-speed analysis

## Design

Evaluation uses held-out test positives removed together with validation positives from the observed graph. Every sampled held-out positive is evaluated, including zero-candidate and missed-positive queries. Scores use Adamic-Adar with deterministic Top-10.

## Recommendation

For the measured directed graph, `5000` is the evidence-based cap: it reaches the maximum candidate coverage (0.9040) and Recall@10 (0.0390) while having the lowest p95 among rows with that quality (23.632 ms). This is a benchmark configuration, not a production default.

## Directed vs mutual

At their selected caps, directed has candidate coverage=0.9040, Recall@10=0.0390, candidates/query=1144.2, and p95=23.632 ms. Mutual has coverage=0.8910, Recall@10=0.1120, candidates/query=858.9, and p95=14.506 ms. These are separate graph semantics, not interchangeable defaults.

## Degree buckets

- directed/5000: slowest observed bucket was 501-1000 (p95=30.269 ms, n=5).
- mutual/5000: slowest observed bucket was 101-500 (p95=15.852 ms, n=408).

## Scope and limitations

The explicit deterministic held-out sample size is 1000; results must not be generalized beyond this data, hardware, seed, and scoring configuration. Scale rows marked `skipped_resource_guard` were not run. Synthetic graphs are heavy-tail stress tests, not production traffic.

## Synthetic scale

- 10000: completed
- 100000: completed
- 500000: skipped_resource_guard
- 1000000: skipped_resource_guard
