export function Steps({ at }: { at: 1 | 2 | 3 }) {
  const items = ["Your details", "Confirm with the SMS code", "Choose a plan"];
  return (
    <div className="steps">
      {items.map((t, i) => (
        <div className="step" key={t}>
          <span className={`dot ${i + 1 < at ? "done" : i + 1 === at ? "on" : ""}`}>{i + 1 < at ? "✓" : i + 1}</span>{t}
        </div>
      ))}
    </div>
  );
}
