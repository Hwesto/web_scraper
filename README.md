# fruit_index — Britain's Fruit Boards

At-a-glance monthly boards for the UK fresh-fruit trade: who supplies Britain, when,
at what landed price, and where each fruit sits in the world. One page per HS code,
built entirely from free public data.

**Live:** https://hwesto.github.io/fruit_index/

## What each board shows
- **Who's landing this month** — origins by share, landed £/kg, with the £/kg & volume
  change vs the same month a year ago.
- **The relay** — who leads UK supply each month of a typical year.
- **The last three years** — monthly import volume (bars) + landed-price trend (line).
- **The price journey** — border → shelf: two measured prices and the spread between them.
- **Where it goes / the world map / domestic market** — destinations, grow→export→import,
  and apparent consumption by country.

The atlas hub (`docs/index.html`) ranks every fruit by import volume with value and a
year-on-year trend.

## Data sources (all free)
- **HMRC** Overseas Trade Statistics — monthly imports / value / re-exports by origin (the anchor).
- **UN Comtrade** + **FAOSTAT** — global trade flows and production.
- **DEFRA** — UK horticulture production + weekly wholesale prices.
- **ONS** Shopping Prices + **Trolley.co.uk** — retail shelf prices (weight-packed by
  weekly scrape; per-each fruit via the ONS index ÷ a sourced standard weight).

Measured ends are kept measured; every model, proxy, override or estimate is labelled.

## Build & test
```
python -m core.build_board      # regenerate every page into docs/
python -m pytest                # run the test suite
```
Data refreshes weekly via GitHub Actions; the pages are static (no JS).
