PYTHON ?= python3
VIVADO ?= vivado
.PHONY: test lint synth icebreaker urbana urbana-rosetta gate-test rom clean

test:
	$(PYTHON) scripts/run_tests.py

lint:
	verilator --lint-only -Wall --top-module dot8_pipeline rtl/dot8_pipeline.sv
	verilator --lint-only -Wall --top-module dot8_serial rtl/dot8_serial.sv

synth:
	$(PYTHON) scripts/synthesize.py

icebreaker:
	$(PYTHON) scripts/build_icebreaker.py

urbana:
	$(VIVADO) -mode batch -source scripts/build_urbana.tcl

urbana-rosetta:
	bash scripts/build_urbana_rosetta.sh

gate-test:
	$(PYTHON) scripts/run_tests.py --core gate-board

rom:
	$(PYTHON) scripts/generate_rom.py

clean:
	rm -rf build
