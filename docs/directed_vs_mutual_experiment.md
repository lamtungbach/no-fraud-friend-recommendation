# Directed vs Mutual classical experiment

## Protocol

This is a reproducible leakage-safe link reconstruction / missing-link proxy, not temporal future friendship prediction.

- Seed: `42`
- Test-positive sample cap per task: `100`
- Ranking policy: evaluate query orientations with a hidden positive in the two-hop pool; uncovered positives count in candidate coverage but are not rankable.

## Task statistics

| Metric | Directed | Mutual |
|---|---:|---:|
| Nodes | 10199 | 10199 |
| Positive links/pairs | 412575 | 85540 |
| Active nodes | 9418 | 9418 |
| Average degree | 80.90499068536131 | 80.90499068536131 |
| Candidate coverage | 0.88 | 1.0 |
| Average candidates/query | 1202.83 | 5383.95 |

## Performance

| Task | Negative | Method | AUC | AP | Recall@10 | NDCG@10 | Hits@10 | MRR |
|---|---|---|---:|---:|---:|---:|---:|---:|
| directed | random | random | 0.4806 | 0.5199 | 0.2841 | 0.1293 | 0.2841 | 0.1196 |
| directed | random | common_neighbors | 0.9110 | 0.9150 | 0.9659 | 0.7160 | 0.9659 | 0.6379 |
| directed | random | jaccard | 0.8786 | 0.8768 | 0.9432 | 0.7011 | 0.9432 | 0.6278 |
| directed | random | adamic_adar | 0.9048 | 0.9113 | 0.9432 | 0.6991 | 0.9432 | 0.6248 |
| directed | random | preferential_attachment | 0.8828 | 0.8969 | 0.8636 | 0.5156 | 0.8636 | 0.4154 |
| directed | hard | random | 0.4649 | 0.4893 | 0.2841 | 0.1420 | 0.2841 | 0.1364 |
| directed | hard | common_neighbors | 0.6837 | 0.6851 | 0.6250 | 0.3779 | 0.6250 | 0.3249 |
| directed | hard | jaccard | 0.6969 | 0.6821 | 0.6477 | 0.3720 | 0.6477 | 0.3098 |
| directed | hard | adamic_adar | 0.6927 | 0.6989 | 0.6591 | 0.3706 | 0.6591 | 0.3024 |
| directed | hard | preferential_attachment | 0.5654 | 0.6235 | 0.4659 | 0.2774 | 0.4659 | 0.2477 |
| mutual | random | random | 0.5655 | 0.5519 | 0.2900 | 0.1308 | 0.2900 | 0.1215 |
| mutual | random | common_neighbors | 0.9943 | 0.9936 | 1.0000 | 0.8328 | 1.0000 | 0.7777 |
| mutual | random | jaccard | 0.9732 | 0.9745 | 0.9950 | 0.7875 | 0.9950 | 0.7202 |
| mutual | random | adamic_adar | 0.9949 | 0.9946 | 1.0000 | 0.8285 | 1.0000 | 0.7719 |
| mutual | random | preferential_attachment | 0.9723 | 0.9710 | 0.9500 | 0.6093 | 0.9500 | 0.5048 |
| mutual | hard | random | 0.5306 | 0.5336 | 0.3300 | 0.1529 | 0.3300 | 0.1360 |
| mutual | hard | common_neighbors | 0.9543 | 0.9410 | 0.9900 | 0.8261 | 0.9900 | 0.7732 |
| mutual | hard | jaccard | 0.9535 | 0.9459 | 0.9500 | 0.7405 | 0.9500 | 0.6754 |
| mutual | hard | adamic_adar | 0.9585 | 0.9459 | 0.9850 | 0.8192 | 0.9850 | 0.7656 |
| mutual | hard | preferential_attachment | 0.8254 | 0.7797 | 0.8850 | 0.4956 | 0.8850 | 0.3805 |

## Interpretation

Random negatives are generally easier than two-hop hard negatives, so a drop under hard negatives is expected rather than evidence of a bug. Mutual remains the closer app proxy for reciprocal friend/chat relationships; directed remains a useful auxiliary benchmark. The final task choice should consider sparsity, candidate coverage, and product semantics alongside metrics.
