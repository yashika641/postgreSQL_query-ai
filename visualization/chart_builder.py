import base64
import decimal
import io

import matplotlib

matplotlib.use("Agg")  # no display available -- this runs inside the API/agent process
import matplotlib.pyplot as plt

MIN_CHART_ROWS = 2   # a single-row aggregate (e.g. COUNT(id)) has nothing to plot
MAX_CHART_ROWS = 50  # matches ResultTable.jsx's MAX_ROWS_SHOWN -- beyond this a bar
                      # chart is unreadable, the table is the better view


def _is_numeric(value) -> bool:
    return isinstance(value, (int, float, decimal.Decimal)) and not isinstance(value, bool)


def _column_types(columns: list[str], rows: list[dict]) -> dict[str, str]:
    types = {}
    for col in columns:
        sample = next((r[col] for r in rows if r.get(col) is not None), None)
        types[col] = "numeric" if _is_numeric(sample) else "other"
    return types


def _render_chart(chart_type: str, x_values: list[str], y_values: list[float],
                   x_label: str, y_label: str, title: str) -> str:
    fig, ax = plt.subplots(figsize=(7, 4))

    if chart_type == "line":
        ax.plot(x_values, y_values, marker="o", color="#4C72B0")
    else:
        ax.bar(x_values, y_values, color="#4C72B0")

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title[:80], fontsize=11)
    if len(x_values) > 8:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def build_chart(question: str, result: dict | None) -> dict | None:
    """Decides whether a query result is worth charting and, if so, renders
    one. Returns None (not a chart-worthy result -- table only) or
    {"chart_type", "x_column", "y_column", "image_base64"}.

    Heuristics, not an LLM call -- this stays fast and deterministic:
    - needs >=2 columns (a single-value aggregate has nothing to plot)
    - needs a row count between MIN_CHART_ROWS and MAX_CHART_ROWS
    - needs at least one numeric column for the y-axis
    - a non-numeric column becomes the x-axis / bar categories; if every
      column is numeric, the other numeric column becomes the x-axis and
      the chart is a line if its name looks like a year/date, else a bar
    """
    if not result:
        return None

    columns = result.get("columns") or []
    rows = result.get("rows") or []

    if len(columns) < 2 or not (MIN_CHART_ROWS <= len(rows) <= MAX_CHART_ROWS):
        return None

    types = _column_types(columns, rows)
    numeric_cols = [c for c in columns if types[c] == "numeric"]
    other_cols = [c for c in columns if types[c] == "other"]

    if not numeric_cols:
        return None

    # prefer a numeric column that isn't an id/key column for the y-axis
    y_col = next((c for c in numeric_cols if not c.lower().endswith("id")), numeric_cols[0])

    if other_cols:
        x_col = other_cols[0]
        chart_type = "bar"
    else:
        remaining = [c for c in numeric_cols if c != y_col]
        if not remaining:
            return None
        x_col = remaining[0]
        chart_type = "line" if any(k in x_col.lower() for k in ("year", "date", "month")) else "bar"

    x_values = [str(r.get(x_col)) for r in rows]
    y_values = [float(r[y_col]) if r.get(y_col) is not None else 0.0 for r in rows]

    image_base64 = _render_chart(chart_type, x_values, y_values, x_col, y_col, question)

    return {
        "chart_type": chart_type,
        "x_column": x_col,
        "y_column": y_col,
        "image_base64": image_base64,
    }


if __name__ == "__main__":
    # sanity check: chart-worthy, single-aggregate (skip), and too-many-rows (skip)

    chartable = {
        "columns": ["tags", "post_count"],
        "rows": [
            {"tags": "python", "post_count": 1200},
            {"tags": "javascript", "post_count": 980},
            {"tags": "sql", "post_count": 640},
        ],
    }
    aggregate = {"columns": ["count"], "rows": [{"count": 993601}]}
    too_many = {
        "columns": ["user_id", "reputation"],
        "rows": [{"user_id": i, "reputation": i * 10} for i in range(100)],
    }

    print("Chartable result:")
    chart = build_chart("posts per tag", chartable)
    print(f"  -> {chart['chart_type']} chart, x={chart['x_column']}, y={chart['y_column']}, "
          f"image bytes (base64): {len(chart['image_base64'])}" if chart else "  -> None (unexpected!)")

    print("Single-aggregate result (should skip):")
    print(f"  -> {build_chart('how many questions', aggregate)}")

    print("Too-many-rows result (should skip):")
    print(f"  -> {build_chart('reputation per user', too_many)}")
