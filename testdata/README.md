# Test data generator

Create BidFile / MarketResult CSV files for feature tests from a single scenario JSON.

- `testdata_builder.html` - form UI. Pick a file type, edit the form, **Save scenario JSON**, or download the CSV directly. **Load scenario JSON** re-opens a saved scenario.
- `generator.py` - same output from the command line / tests: `python generator.py scenarios/bid_sidida.json -o generated`
- `scenarios/` - sample scenarios (`bid_nordic`, `bid_sidida`, `market_result`).

```python
import json
from generator import build

name, text = build(json.load(open("scenarios/bid_sidida.json")))
```

## Scenario format

Common: `fileType` (`bid_nordic` | `bid_sidida` | `market_result`), `periods` (`start`, `resolution` minutes, `count`), `header`, plus type-specific lists
(`portfolios`, `curveOrders`, `blockSubmissions`, `defaultBlocks`, `biddingLevels`, ...). See `scenarios/`.

A volume series is either a plain list, or a compact form that fills the periods (1-based, inclusive):

```json
{"default": "", "ranges": [{"from": 1, "to": 4, "value": -1.4}]}
```

Numbers are written with a decimal comma. Order-period IDs are generated for every non-zero period.

The emitters exist twice (Python and JS in the HTML page). Keep them in sync; `python -m pytest testdata` covers the Python side.
