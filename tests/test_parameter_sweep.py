import asyncio

from runtime_slice.backtest import ParameterSweep


def test_parameter_sweep_isolates_one_failed_combination():
    async def callback(config):
        if config["value"] == 2:
            raise RuntimeError("combination failed")
        return config["value"] * 10

    results = asyncio.run(ParameterSweep().run([{"value": 1}, {"value": 2}, {"value": 3}], callback))
    assert [row["result"] for row in results] == [10, None, 30]
    assert results[1]["error"] == "combination failed"
