PY := python3

.PHONY: all stints rapm system clean site

all: stints rapm system

stints:
	$(PY) src/run_01_stints.py

rapm:
	$(PY) src/run_02_rapm.py

system:
	$(PY) src/run_03_system.py

# Regenerate the GitHub Pages page from README.md. Needs `pip install markdown`.
site:
	$(PY) tools/site.py

clean:
	rm -f figures/*.png output/*.csv data/processed/*
