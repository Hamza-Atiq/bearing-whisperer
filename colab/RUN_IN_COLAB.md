# Run the feature extraction in Google Colab (about 2 to 3 hours, mostly downloading)

Before you start: on your laptop, make a zip of the folders `bearing` and `prereg` together
(select both, right-click, Send to, Compressed folder). Call it `code.zip`.

**Cell 1: upload the code**
```python
from google.colab import files
files.upload()            # choose code.zip
!unzip -o -q code.zip -d /content/p14 && ls /content/p14
```

**Cell 2: tools, and save results to your Google Drive** (so a disconnect loses nothing)
```python
!apt-get -qq install -y unrar > /dev/null && unrar | head -1
from google.colab import drive
drive.mount("/content/drive")
OUT = "/content/drive/MyDrive/p14_features"
```

**Cell 3: one bearing first (a smoke test)**
```python
%cd /content/p14
!python -m bearing.extract --out {OUT} --work /content/work --bearings K001
import pandas as pd
d = pd.read_parquet(f"{OUT}/features_K001.parquet")
print(d.shape, d.usable.mean(), d.groupby("setting").size())
print(d.error.value_counts().head())
print(d[d.setting == "lab"][["condition", "rec", "fe_hz", "residual_db", "tone_outer_minus"]].head())
```
Expected: 400 rows (80 recordings x 5 settings), usable close to 1.0, fe_hz near 100 or 60.
(Checked on the laptop on 16 Oct: K001 gave exactly this, 400 rows, all usable, 23 s of compute.)
If it fails, copy the output to Claude. **Do not continue until this works.**

**Cell 4: all bearings (leave the tab open)**
```python
!python -m bearing.extract --out {OUT} --work /content/work
```
If Colab disconnects, run Cells 1, 2 and 4 again: bearings already saved in your Drive are skipped.

**Cell 5: download the result**
```python
files.download(f"{OUT}/features.parquet")
```
Put the file into `D:\USA Journey\Projects\P-14-motor-current-bearing-fault\data\features.parquet`.
