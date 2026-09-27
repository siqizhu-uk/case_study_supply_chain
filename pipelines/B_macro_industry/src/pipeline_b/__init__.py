"""Pipeline B — macro / industry context series.

None of these observe peripherals or Nordic directly, so they are regime context and sanity checks, never
model regressors that could dominate a 14-quarter panel (see the data-source note). Two series are fetched
and cross-checked against a second primary source; the grade-C documents are quote-checked; the rest of the
note's list is logged in config/data_config.csv with the reason it is manual or rejected.
"""
