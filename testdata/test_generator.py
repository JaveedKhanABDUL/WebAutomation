import json
from pathlib import Path

import pytest

from generator import build, expand_series, FILE_TYPES

SCENARIOS = Path(__file__).parent / "scenarios"


def load(name):
    return json.loads((SCENARIOS / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", FILE_TYPES)
def test_sample_scenarios_build(kind):
    name, text = build(load(kind))
    assert name.endswith(".csv")
    assert text.endswith("\r\n")
    assert ";" in text


def test_bid_sidida_structure():
    name, text = build(load("bid_sidida"))
    lines = text.splitlines()
    assert name == "BidFile_SI-SIDIDA1_PWR-SIDIDA1-D+1_20261024130000_20261014141128.csv"
    assert lines[1] == '"Auction name";PWR-SIDIDA1-D+1'
    assert lines[3] == "PO;ENOS;ENOS-TB01;SI-ELES-IDA1;15;EUR;N"
    assert lines[5] == "PR;Period;OrderPeriodID;Active;Paradoxically;Execution;-9999;9999"
    bl = [ln.split(";") for ln in lines if ln.startswith("BL;")]
    assert [b[3] for b in bl] == ["-5,6", "-5,6"]  # execution = sum of volumes
    assert all(len(b) == 10 + 200 for b in bl)  # 100 volumes + 100 order-period IDs


def test_bid_nordic_header_and_decimals():
    _, text = build(load("bid_nordic"))
    lines = text.splitlines()
    assert lines[:3] == ["Area set;NORDIC", "Auction name;PWR-MRC-D+1", "Auction date time;2022-07-20T10:00:00Z"]
    assert "PR;Period;OrderPeriodID;Active;Execution;-500,0;19,9;20,0;450,0;450,1;600,0;600,1;4000,0" in lines


def test_market_result_series_length_and_ids():
    _, text = build(load("market_result"))
    lines = text.splitlines()
    idx = lines.index("Index prices;15;EUR")
    assert len(lines[idx + 1].split(";")) == 100
    assert lines[idx + 2].split(";")[0] == "13,87"
    block = lines.index("Block order;700000000007834;EPEXSPOT-U01")
    ids = lines[block + 3].split(";")
    assert ids[:4] != [""] * 4 and ids[4] == ""
    assert lines[block + 3] == lines[block + 4]


def test_expand_series_ranges_and_padding():
    assert expand_series({"default": "", "ranges": [{"from": 2, "to": 3, "value": 1.5}]}, 4) == ["", "1,5", "1,5", ""]
    assert expand_series([1, 2], 4, "0") == ["1", "2", "0", "0"]


def test_unknown_file_type():
    with pytest.raises(ValueError):
        build({"fileType": "nope"})
