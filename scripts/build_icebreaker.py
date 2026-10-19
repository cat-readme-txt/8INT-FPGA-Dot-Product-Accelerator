#!/usr/bin/env python3
"""Create an iCEBreaker bitstream with open tools; never programs hardware."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command, log_name):
    log_path = ROOT / "build/icebreaker" / log_name
    with log_path.open("w") as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log_path.read_text()[-6000:])
        raise SystemExit(f"Build failed; inspect {log_path}")
    print(f"Completed {command[0]}; log: {log_path.relative_to(ROOT)}")


def main():
    for executable in ["yosys", "nextpnr-ice40", "icepack"]:
        if not shutil.which(executable):
            raise SystemExit(f"Missing {executable}. Install the OSS CAD Suite or see README.md.")
    destination = ROOT / "build/icebreaker"
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "scripts/generate_rom.py"], cwd=ROOT, check=True)
    run(["yosys", "-Q", "-T", "-p",
         "read_verilog -sv -Irtl rtl/dot8_pipeline.sv rtl/dot8_selftest.sv rtl/icebreaker_top.sv; "
         "synth_ice40 -top icebreaker_top -dsp -json build/icebreaker/design.json; "
         "check -assert; tee -o build/icebreaker/resources.json stat -json; "
         "write_verilog -noattr build/icebreaker/netlist.v"], "synthesis.log")
    run(["nextpnr-ice40", "--up5k", "--package", "sg48", "--freq", "12",
         "--seed", "1", "--json", "build/icebreaker/design.json",
         "--pcf", "constraints/icebreaker.pcf", "--asc", "build/icebreaker/design.asc",
         "--report", "build/icebreaker/timing.json"], "place_route.log")
    run(["icepack", "build/icebreaker/design.asc", "build/icebreaker/icebreaker.bin"], "icepack.log")
    print("Bitstream generated: build/icebreaker/icebreaker.bin")
    print("No FPGA was programmed. The target oscillator is 12 MHz.")


if __name__ == "__main__":
    main()
