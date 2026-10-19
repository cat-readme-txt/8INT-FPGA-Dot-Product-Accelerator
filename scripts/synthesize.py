#!/usr/bin/env python3
"""Map each standalone core to Artix-7 cells and retain resource reports.

This is synthesis, not placement/routing or a clock-frequency measurement.
"""
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not shutil.which("yosys"):
        raise SystemExit("Missing yosys. See README.md for installation.")
    destination = ROOT / "build/reports"
    destination.mkdir(parents=True, exist_ok=True)
    summary = {"target_family": "Xilinx 7-series / Artix-7", "stage": "synthesis_only", "cores": {}}
    for kind in ["pipeline", "serial"]:
        top = f"dot8_{kind}"
        relative_report = f"build/reports/{top}_artix7_resources.json"
        commands = (
            f"read_verilog -sv rtl/{top}.sv; "
            f"synth_xilinx -family xc7 -top {top} -noiopad -noclkbuf; "
            f"check -assert; tee -o {relative_report} stat -json"
        )
        log_path = destination / f"{top}_artix7_synthesis.log"
        with log_path.open("w") as log:
            result = subprocess.run(["yosys", "-Q", "-T", "-p", commands], cwd=ROOT,
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print(log_path.read_text()[-5000:])
            raise SystemExit(f"Synthesis failed for {top}; see {log_path}")
        data = json.loads((ROOT / relative_report).read_text())
        module = data["modules"]["\\" + top]
        cells = module["num_cells_by_type"]
        summary["cores"][kind] = {"num_cells": module["num_cells"], "cells_by_type": cells}
        print(f"{top}: {cells.get('DSP48E1', 0)} DSP48E1; {module['num_cells']} mapped cells total")
    (destination / "artix7_summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
