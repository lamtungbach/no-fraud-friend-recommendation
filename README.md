# Social-Graph PYMK Baselines

Reproducible classical baselines for a People You May Know (PYMK) / link-reconstruction experiment on the public MGTAB benchmark. The project evaluates directed and mutual-link task definitions with leakage-safe splits, two-hop candidates, random and hard negatives, and five topology-based scorers.

This is a research prototype. It evaluates missing-link reconstruction on a graph snapshot; it is **not** a future-friendship prediction system or a production recommendation service.

## Dataset (not included)

This repository deliberately does **not** distribute MGTAB or any raw data. Download the dataset yourself from the [official MGTAB repository](https://github.com/GraphDetec/MGTAB), using the dataset download link in its README. Download **MGTAB** (not MGTAB-large) and comply with the upstream [CC BY-NC-ND 4.0 license](https://creativecommons.org/licenses/by-nc-nd/4.0/).

After extracting the download, copy the six tensor files into the following location:

```text
data/
  raw/
    MGTAB/
      edge_index.pt
      edge_type.pt
      edge_weight.pt
      features.pt
      labels_bot.pt
      labels_stance.pt
```

`data/raw/` is ignored by Git. Do not commit the downloaded tensors, derived per-user exports, or notebook outputs containing individual user IDs.

## Setup

Use Python 3.10+ and create an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The project also requires PyTorch. Install the wheel appropriate for your operating system and hardware from the [official PyTorch installation guide](https://pytorch.org/get-started/locally/), then verify:

```powershell
python -c "import torch; print(torch.__version__)"
```

## Reproduce the experiment

Run these commands from the repository root after placing the data as described above:

```powershell
# Run the test suite.
.\.venv\Scripts\python.exe -m pytest -q

# Validate the adapter and leakage-safe link split.
.\.venv\Scripts\python.exe scripts\validate_mgtab_adapter.py
.\.venv\Scripts\python.exe scripts\build_link_task_stats.py
.\.venv\Scripts\python.exe scripts\validate_link_split.py

# Run the sampled Task 4 benchmark and generate its report.
.\.venv\Scripts\python.exe scripts\run_classical_experiments.py
```

The benchmark writes the main artifacts to:

```text
results/classical_baselines/results.csv
results/classical_baselines/config.json
results/classical_baselines/validation_sanity.json
docs/directed_vs_mutual_experiment.md
```

The default experiment uses seed 42, a 70/15/15 train/validation/test split, and at most 100 test positives per task. See [the experiment report](docs/directed_vs_mutual_experiment.md) for metrics and limitations.

## Project layout

```text
src/          Dataset adapter, link tasks, split/masking, candidates, baselines, evaluation
scripts/      Reproducible validation and experiment entry points
notebooks/    Exploratory analysis notebooks
tests/        Unit tests
docs/         Experiment reports and implementation notes
results/      Generated aggregate results and figures
data/raw/     Local MGTAB download only; ignored by Git
```

## Citation and attribution

If you use MGTAB, cite its authors and follow the dataset's upstream licensing and terms. This repository is an independent baseline implementation and is not affiliated with MGTAB's authors or any employer.
