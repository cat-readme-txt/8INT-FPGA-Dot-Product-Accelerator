# Urbana board build and bring-up

This guide builds the ROM self-test for the [Real Digital Urbana board](https://www.realdigital.org/hardware/urbana), then loads it through the board's USB/JTAG port. The target is the XC7S50-CSGA324-1 Spartan-7. The 100 MHz oscillator, BTN0, and 16 discrete LEDs use the board vendor's [reference constraints](https://www.realdigital.org/downloads/1f07b1146ec59e165634a5b6c782a17d.txt) and [reference manual](https://www.realdigital.org/doc/496fed57c6b275735fe24c85de5718c2). The iCEBreaker `.bin` file and `.pcf` constraints do not apply to Urbana.

The board runs all 64 deterministic dot-product vectors, compares the 19-bit results with independently generated expected values, and latches the result. The test covers the arithmetic pipeline, its input and output handshakes, and deliberate output stalls. The ROM is a demonstration workload; no UART host interface is present.

## Vivado in an Apple Silicon UTM VM

Vivado 2025.2 is an x86-64 Linux application. [UTM's Rosetta support](https://docs.getutm.app/advanced/rosetta/) can run x86-64 Linux programs inside an ARM64 guest that uses the Apple Virtualization backend. In that configuration, `uname -m` still prints `aarch64`; this alone does not rule out a working Vivado installation. The build should use the same Vivado launcher or environment that has already worked in this VM.

The stock Vivado shell launcher may reject `aarch64` before Rosetta reaches its x86-64 executable. If `make urbana` reports `Unsupported architecture: aarch64`, the repository's Tcl script has not run. Resolve the launcher in the VM first, then pass the working Vivado command to `make` using its `VIVADO` variable if the launcher accepts `-mode batch -source ...` arguments. Do not change the VM architecture or reinstall Vivado solely because of this message.

## 1. Get the source into the Debian VM

The original Urbana files are in commit `ee936a7`. The Rosetta build changes in this guide are currently local to the Mac checkout. After reviewing them, publish those changes so the VM can pull the updated script:

```bash
git add Makefile README.md URBANA_BRINGUP.md scripts/build_urbana.tcl
git commit -m "Adapt Urbana Vivado build to Rosetta"
git push origin main
```

Then open a terminal in the VM:

```bash
git clone https://github.com/cat-readme-txt/8INT-FPGA-Dot-Product-Accelerator.git
cd 8INT-FPGA-Dot-Product-Accelerator
git pull --ff-only
git log -1 --oneline
```

If the repository is already cloned, use `git pull --ff-only` from its directory. Verify that `rtl/urbana_top.sv`, `constraints/urbana.xdc`, and `scripts/build_urbana.tcl` exist. The commit ID is useful when recording the test result.

Vivado must include the Spartan-7 device family. In this VM, Vivado 2025.2 is installed under `/home/qihan/amd/2025.2/Vivado`. Use the launcher or desktop entry that produced the HackMidwest bitstream successfully. Inspect the shell's candidates before changing `PATH`:

```bash
type -a vivado
```

Putting the stock `Vivado/bin` directory at the front of `PATH` can bypass a working Rosetta wrapper and trigger `Unsupported architecture: aarch64`. Reuse the working launcher from the previous project. A setup script is optional when the proven launcher already configures the environment.

## 2. Run simulation in Debian

Install the local simulation dependencies once:

```bash
sudo apt-get update
sudo apt-get install -y iverilog python3-venv make
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
make test
```

The expected result is 11 passing RTL tests, including `urbana_top` startup, clock indicator, button restart, and 64-vector completion. Simulation alone does not validate physical pins or routed timing.

## 3. Build the Urbana bitstream in Vivado

In the Debian repository, run `realpath scripts/build_urbana.tcl` to get the exact script path. Launch Vivado through the same method that successfully built HackMidwest. Close any open project, then enter this in Vivado's **Tcl Console**, using the path printed by `realpath`:

```tcl
source /absolute/path/to/8INT-FPGA-Dot-Product-Accelerator/scripts/build_urbana.tcl
```

The script locates its RTL and constraints relative to its own path, so Vivado's current working directory does not matter. Start a fresh Vivado session before retrying after a failed or completed run.

If the proven shell launcher accepts Vivado's `-mode batch -source` arguments, the equivalent terminal build from the repository root is `make urbana`. If the launcher has a different name or path, use `make VIVADO=/full/path/to/working/launcher urbana`. An `Unsupported architecture: aarch64` result from either command means that shell launcher still has not started the Tcl build; use the proven launch method above.

The script follows the same in-process, non-project flow as the proven [HackMidwest Rosetta build](https://github.com/Trade42/HackMidwest/blob/fpga/fpga_board/vivado/build_rosetta.tcl): it synthesizes part `xc7s50csga324-1`, places and routes `urbana_top` with `constraints/urbana.xdc`, writes reports, and creates `build/urbana/urbana_top.bit`. It does not program the board. The run should end with `Urbana bitstream ready:` and nonnegative setup and hold slack. It does not launch separate Vivado child runs or write a routed checkpoint.

The published Urbana constraint file and reference manual both assign the clock to N15. A [published prototype schematic](https://www.realdigital.org/downloads/064514e67fbab05a00650ce69af02486.pdf) labels the clock at P15 instead, so verify the revision of your board and use the heartbeat test below to confirm the clock pin on your hardware. Do not change the XDC pin by guesswork if the heartbeat stays dark.

Before transfer, inspect `build/urbana/timing_summary.rpt` for zero failing endpoints and zero unconstrained internal paths, `build/urbana/drc.rpt` for critical violations, and `build/urbana/io.rpt` for the expected N15 clock, J2 button, and LED pins. The batch script stops if it finds negative worst setup or hold slack; a successful file write alone is not a timing result. Save these reports with the build commit and Vivado version.

## 4. Transfer to the Mac and load volatile configuration

Transfer `build/urbana/urbana_top.bit` to the Mac through a UTM shared directory, `scp`, or another file transfer. For example, if SSH is enabled in Debian and reachable from the Mac:

```bash
scp user@vm-host:/path/to/repo/build/urbana/urbana_top.bit ~/Downloads/
shasum -a 256 ~/Downloads/urbana_top.bit
```

Run `sha256sum build/urbana/urbana_top.bit` in Debian and compare the result. Use the board's **main/programming micro-USB** port with a data-capable cable. Set power jumper J16 to `USB` if this cable supplies power. Leave programming jumper J14 **unloaded** for JTAG mode. The Mac must own the USB device; disconnect it from UTM USB passthrough if the VM captured it. The board's power indicators and green INIT indicator should be on before loading.

On the Mac, install [openFPGALoader](https://trabucayre.github.io/openFPGALoader/guide/first-steps.html) if needed, then detect the FPGA before attempting to load:

```bash
brew install openfpgaloader
openFPGALoader --scan-usb
openFPGALoader -c ft2232 --ftdi-channel 0 --detect
```

The Urbana has an FT2232H USB interface with JTAG on channel A. `openFPGALoader` does not list an `urbana` board profile, so use the cable directly. Confirm that detection reports the XC7S50 before running:

```bash
openFPGALoader -c ft2232 --ftdi-channel 0 --fpga-part xc7s50csga324 ~/Downloads/urbana_top.bit
```

This loads FPGA configuration memory only. It is lost on power-off or when `PROG` is pressed. `--fpga-part` supplies the part for this board without a built-in loader profile. If detection fails, check the cable, J14/J16, UTM USB ownership, and whether another program holds the FTDI interface. Do not use another board's `-b` profile solely because it has the same FPGA package.

If openFPGALoader cannot detect the FTDI/JTAG interface, attach the Urbana USB device to the Debian VM through UTM, open Vivado Hardware Manager, choose **Open Target → Autoconnect**, and use **Program Device** with `build/urbana/urbana_top.bit`. The board manual documents this path. Disconnect the USB device from the Mac's loader before handing it to the VM.

## 5. Read the board result

The board's green **DONE** configuration LED should light after programming. It is separate from the 16 user LEDs and only reports successful configuration. The user LEDs report the design's self-test:

| Indicator | Expected after a pass | Meaning |
| --- | --- | --- |
| LED0 | On | All 64 results matched |
| LED1 | Off | No arithmetic mismatch |
| LED2 | On | Test completed |
| LED9 | On | Count reached 64 (`checked_count[6]`) |
| LED3–LED8 | Off | Lower count bits are zero at 64 |
| LED15 | Blinking | The 100 MHz board clock is running |

Hold BTN0: LED0, LED2, and LED9 should turn off. Release it: the self-test should finish and those LEDs should return on. The 64-vector run completes in microseconds, so the intermediate count is too fast to see by eye. The heartbeat continues while the button is held. The status LEDs are active high; BTN0 is active high.

Record a short video or photos of the pass state and button restart, plus the command output, SHA-256, Vivado reports, board revision, and git commit. If LED15 blinks but LED0 never lights, check LED1 for a mismatch and inspect the simulation and timing reports. If DONE is off, diagnose programming before interpreting user LEDs.

## 6. Optional persistent flash configuration

Only after the volatile load and restart test pass, use the board's QSPI configuration flash if persistent startup is desired. Attach the board's USB device to the Debian VM through UTM for this Vivado step. The board manual identifies a Micron `mt25ql128-spi-x1_x2_x4` configuration device. In Vivado Hardware Manager, add that configuration memory device, generate an MCS file from the **same tested** `.bit` at address 0, and program and verify the device. The [Urbana reference manual](https://www.realdigital.org/doc/496fed57c6b275735fe24c85de5718c2) gives the GUI sequence. Move J14 to the loaded position and power-cycle; DONE should light and the same LED pass pattern should return without JTAG loading.

This step overwrites the current flash image. Preserve any existing image first if it matters. Do not treat a successful JTAG load as evidence that flash startup works; test the power-cycle separately. `openFPGALoader -f` is not the documented Urbana flash procedure, and this repository has no Urbana-specific flash profile.

## Completion record

The project has a physical-board result when the source revision is identified, simulation passes, Vivado implementation meets the 100 MHz constraint without critical DRC issues, the transferred bitstream is verified, and the Urbana shows the pass/count/heartbeat pattern and button restart. Persistent flash startup is an optional additional result. Report the actual Vivado slack and utilization, and keep the old iCE40 results separate from this Spartan-7 implementation.
