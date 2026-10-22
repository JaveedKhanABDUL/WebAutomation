"""Scenario-driven generator for EPEX BidFile / MarketResult test files.

Usage:
    python generator.py scenarios/bid_sidida.json [more.json ...] [-o OUTDIR]

The scenario JSON is the same format that testdata_builder.html saves and loads.
"""
import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

FILE_TYPES = ("bid_nordic", "bid_sidida", "market_result")


def fmt(v):
    """Format a value for the CSV: decimal comma, integral floats without a decimal part."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip().replace(".", ",")


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return 0.0


def fmt_num(x):
    s = f"{round(x, 6):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s.replace(".", ",")


def stamp(iso):
    return re.sub(r"[-:TZ]", "", iso)[:14].ljust(14, "0")


def parse_utc(iso):
    iso = iso.rstrip("Z")
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S" if len(iso) > 16 else "%Y-%m-%dT%H:%M")


def iso_z(iso):
    return parse_utc(iso).strftime("%Y-%m-%dT%H:%M:%SZ") if iso else ""


def period_times(p):
    start, step = parse_utc(p["start"]), timedelta(minutes=int(p.get("resolution", 15)))
    return [(start + i * step).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(int(p["count"]))]


def expand_series(v, n, pad=""):
    """A series is a list of values, or {"default": x, "ranges": [{"from": 1, "to": 4, "value": x}]} (1-based)."""
    if isinstance(v, dict):
        arr = [fmt(v.get("default", pad))] * n
        for r in v.get("ranges", []):
            for i in range(max(1, int(r["from"])) - 1, min(n, int(r["to"]))):
                arr[i] = fmt(r["value"])
    else:
        arr = [fmt(x) for x in (v or [])]
    return (arr + [pad] * n)[:n]


class Ids:
    def __init__(self, start):
        self.n = start

    def next(self):
        self.n += 1
        return str(self.n)


def presence_ids(vols, ids):
    """An order-period ID for every period that carries a non-zero volume."""
    return [ids.next() if v != "" and num(v) != 0 else "" for v in vols]


def build_bid_nordic(s):
    h, times, n = s["header"], period_times(s["periods"]), int(s["periods"]["count"])
    ids, out = Ids(10000100000000), []
    out += [f"Area set;{h['area']}", f"Auction name;{h['auction']}", f"Auction date time;{iso_z(h['auctionDt'])}"]
    for p in s.get("portfolios", []):
        out.append(";".join(["PO", p["member"], p["portfolio"], p["zone"], fmt(p.get("resolution", 60)),
                             p.get("currency", "EUR"), p.get("flag", "N")]))
    for c in s.get("curveOrders", []):
        out.append(";".join(["SL", ids.next(), c["user"], c["member"], iso_z(c["submitted"])]))
        prices = [fmt(x) if "," in fmt(x) else fmt(x) + ",0" for x in c["prices"]]
        out.append(";".join(["PR", "Period", "OrderPeriodID", "Active", "Execution", *prices]))
        for i, r in enumerate(c.get("rows", [])):
            period = iso_z(r["period"]) if r.get("period") else times[i]
            out.append(";".join(["VL", period, ids.next(), c.get("active", "Y"), fmt(r.get("execution", 0)),
                                 *[fmt(x) for x in r.get("volumes", [])]]))
    for sub in s.get("blockSubmissions", []):
        out.append(";".join(["SB", sub["user"], sub["member"], iso_z(sub["submitted"])]))
        out.append(";".join(["BI", "BlockID", "Active", "Execution", "MAR", "AAR", "BlockCode", "BlockCodePRM",
                             "Price", *times, *["OrderPeriodID"] * n]))
        for b in sub.get("blocks", []):
            vols = expand_series(b.get("volumes"), n)
            bid = b.get("id") or ids.next()
            pids = presence_ids(vols, ids)
            out.append(";".join(["BL", str(bid), b.get("active", "Y"), fmt(b.get("execution", "")), fmt(b.get("mar", 1)),
                                 fmt(b.get("aar", 1)), b.get("code", "C01"), fmt(b.get("prm", "")),
                                 fmt(b.get("price", "")), *vols, *pids]))
    name = f"BidFile_{h['area']}_{h['auction']}_{stamp(h['auctionDt'])}_{stamp(h['generatedDt'])}.csv"
    return name, out


def build_bid_sidida(s):
    h, times, n = s["header"], period_times(s["periods"]), int(s["periods"]["count"])
    ids, out = Ids(700000002520000), []
    q = (lambda k: f'"{k}"') if h.get("quoteKeys") else (lambda k: k)
    out += [f"Auction;{h['auction']}", f"{q('Auction name')};{h['auctionName']}",
            f"{q('Auction date time')};{iso_z(h['auctionDt'])}"]
    for p in s.get("portfolios", []):
        out.append(";".join(["PO", p["member"], p["portfolio"], p["biddingLevel"], fmt(p.get("resolution", 15)),
                             p.get("currency", "EUR"), p.get("flag", "N")]))
        for lo in p.get("linearOrders", []):
            par = lo.get("paradoxically", "No")
            out.append(";".join(["SL", str(lo["id"]), lo["user"], lo["member"], iso_z(lo["submitted"])]))
            out.append(";".join(["PR", "Period", "OrderPeriodID", "Active", "Paradoxically", "Execution",
                                 *[fmt(x) for x in lo["prices"]]]))
            for r in lo.get("rows", []):
                out.append(";".join(["VL", iso_z(r["period"]), ids.next(), r.get("active", "Y"), par,
                                     fmt(r.get("execution", 0)), *[fmt(x) for x in r.get("volumes", [])]]))
        for sub in p.get("blockSubmissions", []):
            out.append(";".join(["SB", sub["user"], sub["member"], iso_z(sub["submitted"])]))
            out.append(";".join(["BI", "BlockID", "Active", "Execution", "MAR", "AAR", "BlockCode", "BlockCodePRM",
                                 "Paradoxically", "Price", *times, *times]))
            for b in sub.get("blocks", []):
                vols = expand_series(b.get("volumes"), n)
                ex = fmt(b["execution"]) if b.get("execution") not in (None, "") else fmt_num(sum(num(v) for v in vols))
                pids = presence_ids(vols, ids)
                out.append(";".join(["BL", str(b["id"]), b.get("active", "Y"), ex, fmt(b.get("mar", 1)), fmt(b.get("aar", 1)),
                                     b.get("code", "C01"), fmt(b.get("prm", "")), b.get("paradoxically", "No"),
                                     fmt(b.get("price", "")), *vols, *pids]))
    name = f"BidFile_{h['auction']}_{h['auctionName']}_{stamp(h['auctionDt'])}_{stamp(h['generatedDt'])}.csv"
    return name, out


def build_market_result(s):
    h, m, times, n = s["header"], s.get("market", {}), period_times(s["periods"]), int(s["periods"]["count"])
    res, cur = int(s["periods"].get("resolution", 15)), h.get("currency", "EUR")
    ts, ids, out = ";".join(times), Ids(700000002520000), []

    def series(v):
        return ";".join(expand_series(v, n, "0"))

    out += [f"Auction;{h['auction']}", f"Auction name;{h['auctionName']}", f"Auction date time;{iso_z(h['auctionDt'])}",
            f"Publication date time;{iso_z(h['publicationDt'])}", f"FX rates;{h['fx']}" if h.get("fx") else "FX rates",
            f"Market;{h['market']}",
            f"Index prices;{res};{cur}", ts, series(m.get("indexPrices")),
            f"Index volumes;{res}", ts, series(m.get("indexVolumes")),
            f"Net position;{res}", ts, series(m.get("netPosition"))]
    blocks = s.get("defaultBlocks", [])
    if blocks:
        out += [f"Default blocks;{res};{cur}", ";".join(["Block name", *[b["name"] for b in blocks]]),
                ";".join(["Block price", *[fmt(b["price"]) for b in blocks]]),
                ";".join(["Block volume", *[fmt(b["volume"]) for b in blocks]])]
    for lv in s.get("biddingLevels", []):
        out += [f"Bidding level;{lv['name']}", f"Net position;{res}", ts, series(lv.get("netPosition")),
                f"Imbalance;{res}", ts, series(lv.get("imbalance"))]
    for p in s.get("portfolios", []):
        out.append(";".join(["Portfolio", p["member"], p["portfolio"], fmt(p.get("resolution", res)),
                             p.get("currency", cur), p.get("flag", "N")]))
        orders = [("Linear order;" + o["name"], o) for o in p.get("linearOrders", [])] + \
                 [(f"Block order;{o['id']};{o['user']}", o) for o in p.get("blockOrders", [])]
        for head, o in orders:
            vols = expand_series(o.get("volumes"), n, "0")
            pids = ";".join(ids.next() if num(v) != 0 else "" for v in vols)
            out += [head, ts, ";".join(vols), pids, pids]
    name = f"MarketResult_{h['auction']}_{h['auctionName']}_{stamp(h['auctionDt'])}_{stamp(h['fileDt'])}.csv"
    return name, out


BUILDERS = {"bid_nordic": build_bid_nordic, "bid_sidida": build_bid_sidida, "market_result": build_market_result}


def build(scenario):
    """Return (file_name, text) for a scenario dict."""
    kind = scenario.get("fileType")
    if kind not in BUILDERS:
        raise ValueError(f"fileType must be one of {FILE_TYPES}, got {kind!r}")
    name, lines = BUILDERS[kind](scenario)
    return name, "\r\n".join(lines) + "\r\n"


def write(scenario, outdir):
    name, text = build(scenario)
    path = Path(outdir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("scenarios", nargs="+", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=Path("generated"))
    args = ap.parse_args()
    for sc in args.scenarios:
        print(write(json.loads(sc.read_text(encoding="utf-8")), args.outdir))


if __name__ == "__main__":
    main()
