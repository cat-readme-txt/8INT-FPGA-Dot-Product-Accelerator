"""Exercise the actual integration ROM and sticky board status logic."""
import json
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Timer


async def tick(dut, reset=False):
    dut.clk.value = 0
    dut.rst.value = int(reset)
    await Timer(5, unit="ns")
    dut.clk.value = 1
    await Timer(5, unit="ns")
    dut.clk.value = 0


@cocotb.test()
async def complete_selftest_and_restart(dut):
    for iteration in range(2):
        for _ in range(3):
            await tick(dut, reset=True)
        assert int(dut.done.value) == 0
        assert int(dut.checked_count.value) == 0
        for cycles in range(1024):
            await tick(dut)
            if int(dut.done.value):
                break
        else:
            assert False, "ROM self-test timed out"
        assert int(dut.passed.value) == 1
        assert int(dut.failed.value) == 0
        assert int(dut.checked_count.value) == 64
        for _ in range(20):
            await tick(dut)
            assert int(dut.passed.value) == 1 and int(dut.done.value) == 1
    Path(os.environ["STATS_PATH"]).write_text(json.dumps({
        "core": "selftest", "tests": [{"name": "complete_selftest_and_restart", "passed": True,
                                        "runs": 2, "vectors_per_run": 64,
                                        "completion_cycles": cycles+1}]
    }, indent=2) + "\n")
