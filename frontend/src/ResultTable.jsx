const MAX_ROWS_SHOWN = 50;

function formatCell(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ResultTable({ columns, rows, rowsCount }) {
  if (!columns || columns.length === 0) {
    return <p className="result-empty">Query returned no rows.</p>;
  }

  const shown = rows.slice(0, MAX_ROWS_SHOWN);

  return (
    <div className="result-table-wrap">
      <table className="result-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={col}>{formatCell(row[col])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="result-meta">
        {rowsCount} row{rowsCount === 1 ? "" : "s"}
        {rowsCount > MAX_ROWS_SHOWN
          ? ` (showing first ${MAX_ROWS_SHOWN})`
          : ""}
      </p>
    </div>
  );
}

export default ResultTable;
