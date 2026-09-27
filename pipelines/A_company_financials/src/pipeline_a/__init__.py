"""Company-financial data pipeline (Pipeline A).

Three sources, three trust levels, no API keys, no AI:

* SEC XBRL "company facts" API (data.sec.gov)  -> US filers: Logitech, Ingram Micro, TD Synnex, Amazon.
  Free, no key, User-Agent header only. Structured, legally-liable numbers.
* Company IR PDFs (Nordic, GN)                 -> downloaded from a manifest of URLs, text-extracted with pdfplumber,
  and used to VERIFY the hand-collected CSVs (every figure in data/raw is searched for in the filing text).
* Hand-collected CSVs (data/raw/*.csv)         -> the model's actual inputs; segment lines and verbal metrics that
  no API carries. Each row cites its filing.

Run everything:  python pipelines/A_company_financials/scripts/fetch.py
"""
