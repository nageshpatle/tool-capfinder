# Tool-CapFinder

**Tool-CapFinder** is a data-driven capacitor selection and analysis tool focused on **MLCCs**, with an initial emphasis on **Murata ceramic capacitors**.
It helps engineers filter, compare, and optimize capacitor choices using real electrical parameters rather than just nominal capacitance.

---

## What this project does

* Combines multiple Murata capacitor datasets into a **unified library**
* Adds **ESR**, **SRF**, and **frequency-aware** data where available
* Uses **nominal thickness** (not max) for realistic volume comparison
* Enables filtering by:

  * Package size
  * Capacitance
  * Voltage rating
  * Temperature characteristic
  * Series / codes
* Provides a **Streamlit-based GUI** for interactive exploration
* Supports optimization workflows for power electronics use cases

---

## Repository structure

```
tool-capfinder/
│
├── data/                   # Data files
│   ├── Murata_Unified_Library.csv
│   └── ...
│
├── src/                    # Source code
│   ├── app.py              # Streamlit UI entry point
│   ├── optimizer.py        # Core algorithm
│   ├── scrapers/           # Web scrapers
│   └── processors/         # Data processing scripts
│
├── docs/
│   └── ROADMAP.md          # Future plans
│
├── archive/                # Deprecated files
├── .gitignore
└── README.md
```

> Large intermediate or cache CSVs are intentionally ignored and not tracked.

---

## How to run locally

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

(If `requirements.txt` doesn’t exist yet, install manually:)

```bash
pip install streamlit pandas numpy
```

### 3. Launch the app

Double-click `run_app.bat` or run:
```bash
streamlit run src/app.py
```

---

## Design philosophy

* **Engineering-first**: prioritize real electrical behavior (ESR, SRF, voltage derating)
* **Data transparency**: no black-box scoring
* **Scalable**: designed to extend beyond Murata to other vendors
* **Practical**: optimized for real power electronics design decisions

---

## Roadmap

* Hide advanced options by default (ESR, frequency, min voltage)
* Add one-page flow-based selection UX
* Improve ranking metrics for high-current and high-frequency designs
* Vendor-agnostic support (TDK, Samsung, etc.)
* Cloud-hosted Streamlit deployment

---

## Notes

* This project is under active development.
* Large raw or generated datasets are intentionally excluded from git.
* Contributions, ideas, and feedback are welcome.

---

## License

TBD
