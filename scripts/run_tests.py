#!/usr/bin/env python3
"""Compile actual RTL and run the cocotb suite; exit nonzero on any failure."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", choices=["all", "pipeline", "serial", "selftest", "board", "urbana", "gate-board"], default="all")
    parser.add_argument("--waves", action="store_true")
    args = parser.parse_args()
    executable = "iverilog"
    if not shutil.which(executable):
        raise SystemExit(f"Missing {executable}. See README.md for installation.")
    try:
        from cocotb_tools.runner import get_runner
    except ImportError:
        raise SystemExit("Install the pinned Python dependency: python -m pip install -r requirements.txt")
    subprocess.run([sys.executable, "scripts/generate_rom.py"], cwd=ROOT, check=True)
    reports = ROOT / "build/reports"
    reports.mkdir(parents=True, exist_ok=True)
    jobs = ["pipeline", "serial", "selftest", "board", "urbana"] if args.core == "all" else [args.core]
    for job in jobs:
        top = {"board": "icebreaker_top", "gate-board": "icebreaker_top",
               "urbana": "urbana_top"}.get(job, f"dot8_{job}")
        sources = [ROOT / f"rtl/{top}.sv"]
        if job in ["selftest", "board", "urbana"]:
            sources.insert(0, ROOT / "rtl/dot8_pipeline.sv")
        if job in ["board", "urbana"]:
            sources.insert(1, ROOT / "rtl/dot8_selftest.sv")
        if job == "gate-board":
            netlist = ROOT / "build/icebreaker/netlist.v"
            if not netlist.exists():
                raise SystemExit("Run make icebreaker before make gate-test.")
            candidates = []
            if os.environ.get("YOSYS_DATDIR"):
                candidates.append(Path(os.environ["YOSYS_DATDIR"]) / "ice40/cells_sim.v")
            if shutil.which("yosys"):
                candidates.append(Path(shutil.which("yosys")).resolve().parent.parent / "share/yosys/ice40/cells_sim.v")
            candidates += [Path("/usr/share/yosys/ice40/cells_sim.v"),
                           Path("/usr/local/share/yosys/ice40/cells_sim.v")]
            cells = next((path for path in candidates if path.exists()), None)
            if cells is None:
                raise SystemExit("Set YOSYS_DATDIR to the directory containing ice40/cells_sim.v.")
            sources = [cells, netlist]
        build = ROOT / f"build/icarus/{job}"
        report_name = "icebreaker_post_synthesis" if job == "gate-board" else top
        stats = reports / f"{report_name}_icarus.json"
        stats.unlink(missing_ok=True)
        runner = get_runner("icarus")
        build_args = ["-g2012"]
        runner.build(sources=sources, includes=[ROOT / "rtl"], hdl_toplevel=top,
                     build_dir=build, build_args=build_args, always=True,
                     timescale=("1ns", "1ps"), waves=args.waves,
                     parameters={"HEARTBEAT_BIT": 3} if job == "urbana" else {})
        test_module = ("test_urbana" if job == "urbana" else
                       "test_board" if job in ["board", "gate-board"] else
                       "test_selftest" if job == "selftest" else "test_dot8")
        xml = runner.test(test_module=test_module,
                          hdl_toplevel=top, build_dir=build, test_dir=ROOT / "tests",
                          results_xml=str(build / "results.xml"), waves=args.waves,
                          extra_env={"DUT_KIND": job, "STATS_PATH": str(stats)},
                          seed=20261018)
        tree = ET.parse(xml)
        cases = tree.findall(".//testcase")
        if not cases or tree.findall(".//failure") or tree.findall(".//error"):
            raise SystemExit(f"FAILED: {top}; inspect {xml}")
        data = json.loads(stats.read_text())
        if len(data["tests"]) != len(cases):
            raise SystemExit(f"Missing per-test metrics for {top}")
        print(f"PASS: {top} ({job}): {len(cases)} tests; metrics: {stats.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
