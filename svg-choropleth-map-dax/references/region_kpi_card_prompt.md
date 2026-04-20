# Prompt template — Region KPI Card XL

Use this prompt when asking Claude (desktop, API, or Claude Code) to regenerate the XL card from scratch for a different schema, theme, or layout. It's the exact prompt that produced `region_kpi_card.dax` — battle-tested and produces a working measure on the first try.

Edit the sections marked `★` to match the user's model (metric names, shape table name, color palette) before sending.

---

I need a DAX measure that generates a LARGE SVG KPI card for Power BI (ImageUrl data category).

## CARD LAYOUT
- Canvas: 1100px wide × 600px tall (configurable via `_CardH` variable)
- 2-section layout: MAP on the left, KPIs + Trend stacked vertically on the right
- ALL layout positions must be derived from a CONFIG block at the top of the measure

## CONFIG BLOCK (user-editable variables at the top)
Put these variables at the very start so users can self-service adjust the layout:
```
VAR _CardH      = 600    -- card height
VAR _MapPanelW  = 350    -- map section width
VAR _KpiW       = 700    -- KPI content width
VAR _YAxisW     = 50     -- Y-axis label lane
VAR _ChartH     = 100    -- sparkline height
VAR _RevFs      = 62     -- Revenue/Profit font size
VAR _TileFs     = 38     -- KPI tile value font size
```

## DERIVED LAYOUT (auto-calculated from config)
Below the config, calculate all x/y positions mathematically:
```
VAR _MapSvgW = _MapPanelW - 15
VAR _MapDivX = _MapPanelW + 6
VAR _KX0 = _MapDivX + 12   -- KPI left edge
VAR _KX1 = _KX0 + _KpiW    -- KPI right edge
...etc for all tile positions, trend positions, sparkline positions
```

## LEFT PANEL — CHOROPLETH MAP
- Full height of the card
- Color logic: blue if CY > PY, pink if CY < PY, neutral if equal
- Flat 0.85 opacity for in-region shapes
- Ghost territories at 0.02 opacity for out-of-region shapes

## RIGHT SECTION — STACKED VERTICALLY
Top to bottom:
1. Header: Region name (42px semibold) + subtitle (20px) + YoY chip (25px, 130×44 pill)
2. Revenue / Profit hero numbers (62px bold, deep blue) side by side
3. Three KPI tiles (MARGIN, AVG ORDER VALUE, DISCOUNT) with 38px values
4. 12M Revenue Trend sparkline using full KPI width
   - CY solid line + PY dashed line
   - Area fill under CY
   - Y-axis labels in dedicated 50px lane (0 / 50% / 100% of scale)
   - Month axis: Jan, Apr, Jul, Oct, Dec
   - Legend with CY/PY year labels above the chart

## SPARKLINE PATTERN
Use `FILTER(ALL(dim_calendar[Month]))` to iterate all 12 months regardless of slicer.
Coerce blanks with `+ 0`. Build CY and PY polyline strings via CONCATENATEX.

## KEY DESIGN DECISIONS
- All section dividers are dashed lines (`stroke-dasharray='3 4'`)
- Tile corners are 8px rounded
- The config block comment should say "← edit these variables to resize sections"
- The derived layout comment should say "← calculated automatically, do not edit"
- All viewBox and coordinate FORMAT calls use `"0"` or `"0.0"` / `"0.00"` — NEVER `"0.##"` (trailing dot breaks SVG)
- Use `rgb(...)` color syntax (not `#` hex) to avoid the URL-fragment encoding problem in data URIs

## DATA CATEGORY
Set to ImageUrl.

## MEASURES NEEDED — ★ replace with the user's
`[Total Revenue]`, `[Revenue PY]`, `[Total Profit]`, `[AOV]`, `[Avg Discount %]`

## SHAPES TABLE — ★ replace name if different
`Dim_RegionShapes` with columns: Code, US_Region, Path, MinX, MinY, MaxX, MaxY

## COLOR PALETTE
- Accent positive: `rgb(61,116,169)`
- Accent negative: `rgb(255,57,121)`
- Ink: `rgb(26,39,64)`
- Deep blue: `rgb(12,81,148)`
- Muted: `rgb(135,148,171)`
- Tile bg: `rgb(244,246,249)`
- Lines: `rgb(232,238,245)`
- PY line: `rgb(160,175,198)`
