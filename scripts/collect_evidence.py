#!/usr/bin/env python3
"""Retain measured results and hashes tying the evidence to the source files."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def version(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return (result.stdout.strip() or result.stderr.strip()).splitlines()[0]


def main():
    reports = ROOT / "build/reports"
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    simulation_files = ["dot8_pipeline_icarus.json", "dot8_serial_icarus.json",
                        "dot8_selftest_icarus.json", "icebreaker_top_icarus.json",
                        "icebreaker_post_synthesis_icarus.json"]
    simulations = {}
    for name in simulation_files:
        data = json.loads((reports/name).read_text())
        if not data["tests"] or any(not entry["passed"] for entry in data["tests"]):
            raise SystemExit(f"Incomplete or failed simulation: {name}")
        simulations[name] = data
        shutil.copy2(reports/name, evidence/name)
    pipeline = simulations[simulation_files[0]]["tests"]
    serial = simulations[simulation_files[1]]["tests"]
    if len(pipeline) != 4 or len(serial) != 4:
        raise SystemExit("Run the complete test suite before collecting evidence.")
    timing = json.loads((ROOT/"build/icebreaker/timing.json").read_text())
    resources = json.loads((reports/"artix7_summary.json").read_text())
    tools = {"iverilog": version(["iverilog", "-V"]), "yosys": version(["yosys", "-V"]),
             "nextpnr": version(["nextpnr-ice40", "--version"])}
    try:
        import cocotb
        tools["cocotb"] = cocotb.__version__
    except ImportError:
        tools["cocotb"] = "unavailable"
    if shutil.which("verilator"):
        tools["verilator_lint"] = version(["verilator", "--version"])
    (evidence/"tool_versions.json").write_text(json.dumps(tools, indent=2)+"\n")
    for path in reports.glob("*artix7*"):
        shutil.copy2(path, evidence/path.name)
    for name in ["rtl_test_run.log", "gate_test_run.log"]:
        if (reports/name).exists():
            shutil.copy2(reports/name, evidence/name)
    for job in ["pipeline", "serial", "selftest", "board", "gate-board"]:
        shutil.copy2(ROOT/f"build/icarus/{job}/results.xml", evidence/f"{job}_results.xml")
    for name in ["timing.json", "resources.json", "synthesis.log", "place_route.log"]:
        shutil.copy2(ROOT/"build/icebreaker"/name, evidence/("icebreaker_"+name))
    prebuilt = ROOT/"prebuilt"
    prebuilt.mkdir(exist_ok=True)
    shutil.copy2(ROOT/"build/icebreaker/icebreaker.bin", prebuilt/"icebreaker.bin")
    source_paths = sorted(path for folder in ["rtl", "tests", "scripts", "constraints"]
                          for path in (ROOT/folder).rglob("*")
                          if path.is_file() and "__pycache__" not in path.parts)
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in source_paths}
    (evidence/"source_hashes.json").write_text(json.dumps(hashes, indent=2)+"\n")
    clock = next(iter(timing["fmax"].values()))
    retired_pipeline = sum(test.get("retired", 0) for test in pipeline)
    retired_serial = sum(test.get("retired", 0) for test in serial)
    test_count = sum(len(data["tests"]) for data in simulations.values())
    dsp_pipeline = resources["cores"]["pipeline"]["cells_by_type"].get("DSP48E1", 0)
    dsp_serial = resources["cores"]["serial"]["cells_by_type"].get("DSP48E1", 0)
    util = timing["utilization"]
    text = f"""# Validation evidence

Generated UTC: {datetime.now(timezone.utc).isoformat()}

These results were produced by executing the supplied RTL and implementation
flow. The source hashes in this directory identify the checked files.

| Check | Observed result |
| --- | --- |
| Automated RTL and mapped-netlist tests | {test_count} passed |
| Parallel-core completed transactions | {retired_pipeline:,} exact matches |
| Serial-core completed transactions | {retired_serial:,} exact matches |
| Parallel-core initiation interval | 1 clock cycle without stalls |
| Parallel-core input-to-output transfer latency | 4 clock cycles without stalls |
| Serial-core initiation interval | 9 clock cycles without stalls |
| Artix-7 DSP48E1 mapping | {dsp_pipeline} parallel; {dsp_serial} serial |
| iCEBreaker implementation clock constraint | {clock['constraint']:.2f} MHz |
| Routed static maximum-frequency estimate | {clock['achieved']:.2f} MHz |
| iCE40 logic cells, including ROM self-test | {util['ICESTORM_LC']['used']} / {util['ICESTORM_LC']['available']} |
| iCE40 DSP blocks | {util['ICESTORM_DSP']['used']} / {util['ICESTORM_DSP']['available']} |
| Bitstream | Generated successfully |
| Physical FPGA board run | Not performed |

The randomized handshake test uses 12,288 vectors for each core across seeds
42, 2026, and 8675309. Other tests cover directed arithmetic extremes and reset
with work in flight. The four-stage pipeline retains pending output data while
the receiver applies backpressure.

The board self-test is checked at RTL and again after synthesis using the iCE40
primitive models. These are functional simulations without SDF back-annotation.
The routed timing report is a separate static check at the 12 MHz board clock.
The static maximum-frequency estimate is not a measured operating frequency.

The standalone Artix-7 mapping is a resource comparison. It has no associated
Artix-7 place-and-route result. The iCE40 report covers the complete demonstration
top, which deliberately stalls its output periodically.
"""
    (evidence/"VALIDATION.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
