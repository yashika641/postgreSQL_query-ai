function ChartView({ chartType, xColumn, yColumn, imageBase64 }) {
  if (!imageBase64) return null;

  return (
    <div className="chart-wrap">
      <img
        src={`data:image/png;base64,${imageBase64}`}
        alt={`${chartType} chart of ${yColumn} by ${xColumn}`}
      />
    </div>
  );
}

export default ChartView;
