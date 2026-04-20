---
name: svg-choropleth-map-dax
description: Build Power BI SVG choropleth maps from ANY SVG source (country, state, custom territories) using DAX ImageUrl measures. Supports dynamic viewBox zoom, regional drill-down, per-region KPI cards with mini-maps. Use when the user asks to "create an SVG map in Power BI", "build a choropleth with DAX", "add a geo map without Bing", "make a regional heatmap", "SVG map of <anywhere>", or wants to turn any SVG file into an interactive Power BI map.
---

# SVG Choropleth Maps in Power BI via DAX

Turn any SVG map (country, US states, custom sales territories, school districts, anything with polygon regions) into an interactive Power BI visualization. Pure DAX — no custom visual, no Bing Maps, no internet.

Credit: technique originated by Andrzej Leszkiewicz (Poland SVG Map, CC BY 4.0). This skill extends it with dynamic viewBox zoom, adaptive sizing, robust extraction, and fixes for known rendering bugs.

## What the user needs before starting

Ask the user for these four things up front:

1. **An SVG file of the map** — each region must be a separate `<path>` element. Good free sources: [simplemaps.com](https://simplemaps.com/resources), Wikimedia Commons, [mapsvg.com free maps](https://mapsvg.com). If the SVG is one giant path or a raster trace, it won't work.
2. **A key that links shapes to their data** — e.g. state abbreviation, ISO code, custom territory ID. Must match whatever column exists in the user's fact/dim tables.
3. **Optional grouping column** — if they want regional drill-down (e.g. US_Region, Continent, Sales_Zone), they need a way to classify each shape into a group.
4. **The metric(s) to visualize** — a measure like `[Total Revenue]`, `[YoY Growth]`, `[Attainment %]`.

If any of these are missing, stop and ask. Don't guess.

## The 5-step workflow

### Step 1 — Inspect the SVG

Open the SVG in a text editor. Verify:
- Each region is its own `<path>` (not a `<polygon>`, `<g>` group of lines, or `<image>`).
- Each path has an identifier — usually `id=""` or `data-name=""` or a nested `<title>`.
- Paths use absolute or relative coordinates (both work).

If paths lack identifiers, the user must add them manually or the extraction will produce anonymous shapes.

Example of a usable path:
```xml
<path id="CA" name="California" d="M123.4 56.7L..." />
```

### Step 2 — Extract paths to CSV

Use `references/extract_svg_paths.py`. It:
- Parses the SVG with ElementTree
- Computes per-path bounding boxes by tokenizing the `d=` string (needed for zoom)
- Writes UTF-8 BOM CSV so Power Query handles it cleanly

Run:
```bash
python extract_svg_paths.py input.svg output.csv
```

The user can edit the script to add grouping logic (e.g. classify US states into North/South/East/West). The template has an example for US states.

Output CSV columns:

| Column | Purpose |
|--------|---------|
| `Code` | Unique region key (from `id` attribute) |
| `Name` | Display name (from `name` attribute or `<title>`) |
| `Group` | Optional higher-level grouping |
| `MinX, MinY, MaxX, MaxY` | Bounding box — **essential for zoom** |
| `Path` | The raw SVG `d=` string |

### Step 3 — Load into Power BI

1. Get Data → Text/CSV → point at the output file.
2. Rename the table (e.g. `Dim_Shapes`, `Dim_Territories`).
3. Create a relationship: `Dim_Shapes[Code]` (one) ↔ `YourDim[Code]` (many). Single direction filter from the shapes dim outward is usually fine.
4. Don't hide `Path`, `MinX/Y`, `MaxX/Y` — the measure needs to read them.

### Step 4 — Paste the DAX measure

Copy `references/svg_map_measure.dax` into the model. Customize:
- Replace `'Dim_Shapes'` with your table name.
- Replace `[Total Revenue]` with your metric.
- Replace `'YourDim'[Group]` with your grouping column (if using regional drill).
- Adjust `_FillSelected` / `_FillUnselected` colors.

**Then set `dataCategory = "ImageUrl"` on the measure.** Without this, Power BI renders the raw SVG string as text. (In Model view → select measure → Properties → Data category.)

### Step 5 — Use in visuals

Drop the measure into:
- **New Card** (no row context) → full map.
- **Matrix** with `Code` on rows → one row per region, each cell shows that region highlighted.
- **Card with region slicer** → dynamic zoom to whatever the user selects.

In the visual format pane, set image size explicitly (e.g. 400×300). Don't let it auto-size.

## The six non-obvious design decisions

When building or adapting the measure, these are the things that will bite without explanation.

### 1. Use `FILTER(ALL(table), predicate)` for scope, not `IF`

`IF` can't return a table in DAX. To build a dynamic subset:
```dax
VAR _Scope =
    FILTER (
        ALL ( 'Dim_Shapes' ),
        NOT _HasOneGroup || 'Dim_Shapes'[Group] = _SelectedGroup
    )
```
The `NOT _HasOneGroup || ...` predicate short-circuits: no selection → all rows pass; single selection → only matching rows pass.

### 2. `ALL(table)` beats `ALL(col1, col2, ...)`

The simpler form is more reliable. With multi-column `ALL`, it's easy to accidentally project away a column you later need for `MINX`/`MAXX`, or trigger the "multiple columns" error when `CALCULATE` does context transition on a row containing wide string columns like `Path`.

### 3. Use `TREATAS` for metric lookup inside the iterator

```dax
CALCULATE ( [Total Revenue], TREATAS ( { _ThisCode }, 'Dim_Shapes'[Code] ) )
```
Avoids the "cannot convert multi-column row to scalar" error that implicit context transition causes when a row has `Path` (a long string) among its columns.

### 4. Selection detection must fall back across tables

If the visual is filtered through a dimension table, `SELECTEDVALUE` on the shapes table returns blank.
```dax
VAR _SelGroupShapes = SELECTEDVALUE ( 'Dim_Shapes'[Group] )
VAR _SelGroupDim    = SELECTEDVALUE ( 'dim_regions'[Group] )
VAR _SelectedGroup  = COALESCE ( _SelGroupShapes, _SelGroupDim )
```

### 5. **Never use `FORMAT(x, "0.##")` for SVG numeric attributes**

This is THE bug that wastes the most debugging time. `FORMAT(458.0, "0.##")` returns `"458."` — a trailing dot with no digit. Some SVG renderers (including Power BI's image host) reject `viewBox='756.9 458. 165.4 239.9'` as invalid and silently render a blank image.

**Always use `"0.00"` or `"0.0#"`** in viewBox and other numeric SVG attributes. Build it into muscle memory — this is non-negotiable.

### 6. Adaptive output dimensions preserve aspect ratio

A wide region (east-west stretch) and a tall region (north-south stretch) should not emit the same-sized SVG. Let the max dimension drive:
```dax
VAR _MaxDim = 500
VAR _AspectScale = DIVIDE ( _MaxDim, IF ( _VBW > _VBH, _VBW, _VBH ) )
VAR _OutW = ROUND ( _VBW * _AspectScale, 0 )
VAR _OutH = ROUND ( _VBH * _AspectScale, 0 )
```
This avoids squash/clip issues when the matrix cell aspect ratio doesn't match the content.

## Advanced pattern — Region KPI Card XL

Once the map works, a natural next step is a **per-region KPI card** combining a mini-map, headline metrics, and a sparkline — all rendered as a single SVG ImageUrl measure.

See `references/region_kpi_card.dax` for the production template (1100×600 canvas). Architecture:

- **Fixed outer viewBox** (`0 0 1100 {cardH}` — card coordinates).
- **Config block at the top** — the user edits `_CardH`, `_MapPanelW`, `_KpiW`, font sizes, etc. to resize.
- **Derived layout block** — all x/y positions math'd from config (never hardcoded downstream).
- **Nested `<svg>`** for the map with its own per-region viewBox.
- Headline metrics (Revenue, Profit) at 62px; three tile KPIs (Margin, AOV, Discount) at 38px.
- 12-month CY + PY sparkline with area fill, dots, legend, Y-axis labels, and month ticks.

`references/region_kpi_card_prompt.md` is the **prompt template** that produced this measure — use it when regenerating the card for a different schema or theme. It bakes in all the design decisions and gotchas so Claude produces a working measure first try.

Use this when the user wants a matrix of region cards instead of (or in addition to) a choropleth map.

### Sparkline-specific gotchas

- Coerce blanks with `[Total Revenue] + 0` — missing months break the polyline.
- Use `FILTER(ALL(calendar[Month]))` to iterate all 12 months regardless of slicer selection.
- Guard against `_Scale = 0` (all zero) by wrapping with `MAX(..., 1)` before using it as a denominator.

### Prefer `rgb()` over `#hex` inside data URIs

Both work for the `<svg>` root, but `#` is a URI fragment separator inside `data:image/svg+xml;utf8,` payloads. Older guidance says to URL-encode `#` as `%23` — that works, but it's fragile. Cleaner: use `rgb(r,g,b)` / `rgba(r,g,b,a)` syntax everywhere. No encoding needed, no surprises when a teammate copies a hex code from a design tool.

### Choropleth coloring against a comparison baseline

For a YoY-comparison map, color by direction rather than intensity:

```dax
VAR _FC =
    IF (
        NOT _InRegion,
        _MapFill,                                    -- ghost territories
        SWITCH ( TRUE (),
            _CurrentRevenue > _PY_Revenue, "rgb(61,116,169)",    -- up = blue
            _CurrentRevenue < _PY_Revenue, "rgb(255,57,121)",    -- down = pink
            "rgb(29,113,149)"                                    -- flat = neutral
        )
    )
```

Combined with flat fill-opacity (0.85 for in-region, 0.02 for ghost), this reads instantly: "which states grew, which shrank". Avoid doing *both* direction AND intensity — too much visual information competes for attention.

### The 32 KB limit

Power BI truncates ImageUrl values at ~32 KB. If a region has many shapes (e.g. including every Canadian arctic territory, each with thousands of path points), you will exceed this. Mitigations:

- Exclude visually-negligible detailed shapes (`NOT IN {"NU", "NT"}` for arctic territories).
- Simplify paths at extraction time using [mapshaper](https://mapshaper.org/) before running the Python extractor.
- Drop to fewer decimal places in the path coordinates (strip via regex during extraction).

## Debugging: the diagnostic query

When a region renders blank, don't guess — inspect. Paste this into DAX Query View:

```dax
EVALUATE
SUMMARIZECOLUMNS (
    'Dim_Shapes'[Group],
    "scope_rows", CALCULATE ( COUNTROWS ( 'Dim_Shapes' ) ),
    "svg_len", LEN ( [SVG Map] ),
    "svg_first_400", LEFT ( [SVG Map], 400 ),
    "total_metric", [Total Revenue]
)
```

What each column tells you:
- **`scope_rows` = 0** → `_SelectedGroup` doesn't match any shapes. Check spelling, check which table is filtering.
- **`svg_len` < 500** → scope is empty or paths aren't emitting. Check `_Scope`.
- **`svg_first_400`** → read the viewBox. Look for `458.` (trailing dot) or out-of-range values.
- **`total_metric` = BLANK** → data mismatch between `Dim_Shapes[Code]` and your fact's join key. The map path will render but color won't.

## Reference files

All templates are in `references/`:

- `svg_map_measure.dax` — canonical choropleth measure with dynamic zoom.
- `svg_map_single_region.dax` — isolated test measure hardcoded to one group (for debugging).
- `region_kpi_card.dax` — production-grade 1100×600 card combining mini-map + KPIs + CY/PY sparkline with config-driven layout.
- `region_kpi_card_prompt.md` — the prompt template that produced the card above. Use when regenerating for different schema/theme.
- `extract_svg_paths.py` — Python SVG → CSV extractor with bbox computation.
- `diagnostic.dax` — the query above, ready to copy.

## Checklist the user can run

- [ ] SVG has per-region `<path>` elements with unique IDs
- [ ] Python extractor produces CSV with `Code, Name, MinX/Y, MaxX/Y, Path`
- [ ] Shapes table loaded; relationship to dim/fact on `Code` established
- [ ] Measure uses `FORMAT(..., "0.00")` — NEVER `"0.##"` — for viewBox
- [ ] Measure uses `TREATAS` for metric lookup (not implicit context transition)
- [ ] `_SelectedGroup` uses `COALESCE` across tables
- [ ] `dataCategory = "ImageUrl"` set on the measure
- [ ] Image size set explicitly on the visual format pane
- [ ] If using KPI cards: prefer `rgb()` over `#hex` colors; blanks coerced with `+ 0`; config block at top for resize
- [ ] Each region's SVG output stays under 32 KB

## Questions to ask when the pattern isn't working

1. **Blank render?** → run the diagnostic query. Check viewBox for trailing dots.
2. **Wrong region highlighted?** → check selection detection. Is the slicer on the shapes table or a related dim?
3. **Choropleth colors all the same?** → `_MetricMax` is coming back as 0 or BLANK. Check the fact-to-dim join.
4. **Truncated SVG?** → hit the 32 KB limit. Simplify paths with mapshaper.
5. **Squashed or clipped shape?** → adaptive sizing not wired up. Check `_OutW`/`_OutH` calculation.
