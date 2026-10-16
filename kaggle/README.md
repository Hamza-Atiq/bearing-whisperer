# How the feature table was made (Kaggle)

1. Our code only (`bearing/`, `prereg/`) was uploaded as a private Kaggle dataset `hamzaatique/p14-bearing-code`
   (metadata: `code-dataset-metadata.json`). No data, no keys.
2. `run_features.py` ran as a private Kaggle script with internet on (`kernel-metadata.json`). It checks that the
   rules file is the frozen one (fingerprint `383402e7...173e`), downloads each Paderborn bearing, makes the
   features, deletes the raw files, and saves `features.parquet` (derived from CC BY-NC 4.0 data).
3. The table was downloaded into `data/features.parquet` (not published; `data/` is git-ignored).

To re-run: `kaggle datasets version -p <folder with bearing/ prereg/ and dataset-metadata.json> -m "..."`, then
`kaggle kernels push -p <folder with run_features.py and kernel-metadata.json>`.
