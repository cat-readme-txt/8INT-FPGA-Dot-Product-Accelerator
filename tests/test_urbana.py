"""Exercise the Urbana pin-level status and active-high restart button."""
import json
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Timer


async def tick(dut, pressed=False):
    dut.clk_100mhz.value = 0
    dut.btn0.value = int(pressed)
    await Timer(5, unit="ns")
    dut.clk_100mhz.value = 1
    await Timer(5, unit="ns")
    dut.clk_100mhz.value = 0


@cocotb.test()
async def startup_status_clock_and_restart(dut):
    dut.clk_100mhz.value = 0
    dut.btn0.value = 0
    for cycles in range(512):
        await tick(dut)
        if int(dut.led.value) & 1:
            break
    else:
        assert False, "Urbana self-test never passed"

    status = int(dut.led.value)
    assert status & 0x207 == 0x205  # pass, done, and 64 checked; no mismatch
    assert status & 0x7c00 == 0

    heartbeat_before = (status >> 15) & 1
    for _ in range(8):
        await tick(dut)
    assert (int(dut.led.value) >> 15) & 1 != heartbeat_before

    for _ in range(4):
        await tick(dut, pressed=True)
    assert int(dut.led.value) & 0x3ff == 0
    for _ in range(512):
        await tick(dut)
        if int(dut.led.value) & 1:
            break
    else:
        assert False, "Urbana self-test did not restart"
    assert int(dut.led.value) & 0x207 == 0x205

    Path(os.environ["STATS_PATH"]).write_text(json.dumps({
        "core": "urbana", "tests": [{
            "name": "startup_status_clock_and_restart", "passed": True,
            "completed_selftests": 2, "vectors_per_run": 64
        }]
    }, indent=2) + "\n")
