# INT8 dot-product accelerator

An eight-lane signed INT8 dot-product engine written in synthesizable SystemVerilog.
The repository includes a four-stage streaming pipeline, a one-multiplier serial
baseline, and ROM-driven self-tests for the standard iCEBreaker and Real Digital
Urbana boards. The cocotb suite checks the RTL against a Python integer
reference. Simulation and FPGA builds do not require hardware; neither board
implementation has been tested on a physical board yet.

The [pre-Urbana validation report](evidence/VALIDATION.md) records ten RTL tests,
one synthesized-netlist test, and 13,846 exact output matches per arithmetic
core. The accompanying [tool versions](evidence/tool_versions.json) and
[source hashes](evidence/source_hashes.json) identify the recorded run.
See [technical notes](TECHNICAL_NOTES.md) for the architecture and measurement
scope.

## Build and test

From the repository root on Ubuntu or Debian, install the open-source FPGA
tools and Python dependency:

```bash
sudo apt-get update
sudo apt-get install -y iverilog yosys nextpnr-ice40 fpga-icestorm python3-venv make
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
make test
```

`make test` runs eleven RTL tests: four per arithmetic core, one for the self-test,
and one for each board top. The test runner exits with an error if any test
fails. Per-test transaction counts are written to `build/reports/`.

Then run the implementation flow:

```bash
make synth
make icebreaker
make gate-test
```

`make synth` reports resource use for the standalone cores mapped to Xilinx
7-series primitives. `make icebreaker` builds the separate iCE40 board application
through place-and-route. `make gate-test` runs an additional test on its mapped
netlist with the Yosys iCE40 primitive models. No command above programs a board.

For a Real Digital Urbana, use the [Urbana build and bring-up guide](URBANA_BRINGUP.md).
The separate `make urbana` target requires Vivado with Spartan-7 support and
generates a `.bit` file plus routed timing, utilization, DRC, and I/O reports.
The same Tcl script can run from a working Vivado GUI session in a Rosetta VM.

## Other platforms and tool installations

[OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases) provides
the FPGA tools for systems without package-manager access and publishes builds
for Linux and macOS. Download the archive matching your host platform, extract
it into a directory you own, and load its tool environment. For example:

```bash
source "$HOME/oss-cad-suite/environment"
cd /path/to/this/repository
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
make test
```

Adjust both paths to the local installation and repository. Load the tool
environment before activating the Python virtual environment.

If `make gate-test` cannot locate the primitive models, set `YOSYS_DATDIR` to the
directory containing `ice40/cells_sim.v`, then rerun it:

```bash
export YOSYS_DATDIR="$HOME/oss-cad-suite/share/yosys"
make gate-test
```

## Source map

| File | Purpose |
| --- | --- |
| [`rtl/dot8_pipeline.sv`](rtl/dot8_pipeline.sv) | Four-stage arithmetic pipeline with global stall control |
| [`rtl/dot8_serial.sv`](rtl/dot8_serial.sv) | One-multiplier baseline with an input-load cycle |
| [`tests/test_dot8.py`](tests/test_dot8.py) | Arithmetic reference and transaction scoreboard |
| [`rtl/dot8_selftest.sv`](rtl/dot8_selftest.sv) | ROM-driven self-test with deliberate output stalls |
| [`rtl/icebreaker_top.sv`](rtl/icebreaker_top.sv) | Board startup reset and synchronized user button |
| [`rtl/urbana_top.sv`](rtl/urbana_top.sv) | Urbana 100 MHz self-test, LEDs, and button restart |
| [`constraints/urbana.xdc`](constraints/urbana.xdc) | Urbana clock, button, and LED pin assignments |
| [`scripts/build_urbana.tcl`](scripts/build_urbana.tcl) | In-process Vivado Spartan-7 implementation and report generation |
| [`rtl/selftest_rom.svh`](rtl/selftest_rom.svh) | Generated test vectors with independent Python answers |
| [`scripts/build_icebreaker.py`](scripts/build_icebreaker.py) | Full open-source FPGA implementation flow |
| [`evidence/VALIDATION.md`](evidence/VALIDATION.md) | Retained tests, implementation results, and measurement limits |
| [`TECHNICAL_NOTES.md`](TECHNICAL_NOTES.md) | Arithmetic, flow control, verification, and FPGA mapping |

## Interface contract

`a_flat[8*i +: 8]` contains signed lane `i`; lane zero is the least-significant
byte. The same packing applies to `b_flat`. `out_data` is a signed 19-bit integer.

An input transfer occurs at a rising clock edge with `in_valid && in_ready`.
An output transfer occurs with `out_valid && out_ready`. A producer must keep
its payload and valid signal stable until acceptance. The accelerator holds its
output stable while the receiver applies backpressure.

`rst` is active high. It clears control state at the rising edge and suppresses
handshakes while asserted. Reset cancels outstanding work; canceled transactions
produce no later outputs. Datapath registers do not need reset because validity
determines whether their contents may be consumed.

| Core | No-stall transfer latency | No-stall initiation interval |
| --- | --- | --- |
| Pipeline | 4 clock cycles | 1 clock cycle |
| Serial baseline | 9 clock cycles | 9 clock cycles |

Latency here means the difference between the input-handshake edge and the
output-handshake edge. Backpressure can extend wall-clock latency.

## iCEBreaker demonstration

The included constraints target the **standard iCEBreaker iCE40UP5K-SG48** with
its 12 MHz oscillator. They do not target iCEBreaker Bitsy or unrelated boards.
The core itself is portable; other boards need their own top-level integration
and pin constraints.

`make icebreaker` generates `build/icebreaker/icebreaker.bin`. The repository
also includes `prebuilt/icebreaker.bin`; it has not been run on hardware.
Rebuilding locally produces a bitstream from the current source and tools.

With the matching board connected, the optional command below loads volatile
configuration through the IceStorm programmer:

```bash
iceprog -S build/icebreaker/icebreaker.bin
```

The green user LED illuminates after all 64 test vectors pass. A red user LED
indicates a mismatch. Press the user button to restart the self-test. The test
includes a negative-extreme arithmetic case and periodic output stalls.

No connected-board test is recorded. The FPGA result comes from place-and-route
and functional mapped-netlist simulation, without SDF delay annotation.

## Urbana demonstration

The [Urbana guide](URBANA_BRINGUP.md) covers GitHub transfer to a Debian Vivado
VM, local simulation, 100 MHz routed implementation, bitstream transfer to a
Mac, volatile USB/JTAG loading with openFPGALoader, and optional persistent
flash programming. The Urbana design runs the same 64-vector self-test and
exposes pass, fail, completion, checked count, and clock heartbeat on user LEDs.
The physical board and Vivado build still need to be run.

## Extra commands

```bash
python scripts/run_tests.py --core pipeline
python scripts/run_tests.py --core serial
python scripts/run_tests.py --core pipeline --waves
```

Waveforms are placed under the simulator build directory. If Verilator is
installed, `make lint` performs strict RTL lint on both arithmetic cores.
Simulation uses Icarus Verilog with the pinned cocotb dependency.

After rerunning the full flow, `python scripts/collect_evidence.py` refreshes the
retained validation evidence. Simulation seeds are fixed for reproducibility.
Tool versions can change synthesis cell counts or placement results.

## References

- [cocotb 2.0 Python runner](https://docs.cocotb.org/en/v2.0.0/runner.html)
- [OSS CAD Suite installation](https://github.com/YosysHQ/oss-cad-suite-build)
- [Yosys and nextpnr implementation flow](https://github.com/YosysHQ/nextpnr)
- [iCEBreaker hardware documentation](https://docs.icebreaker-fpga.org/hardware/icebreaker/)
- [Reference iCEBreaker pin assignments](https://github.com/YosysHQ/icestorm/blob/main/examples/icebreaker/icebreaker.pcf)

## License

This project is available under the [MIT License](LICENSE).
