interface OutputPanelProps {
  output: string;
  onClear: () => void;
}

export function OutputPanel({ output, onClear }: OutputPanelProps) {
  return (
    <section className="panel output-panel">
      <div className="panel-title row">
        <div>
          <span>Result</span>
          <h2>Last Command Output</h2>
        </div>
        <button className="button quiet" type="button" onClick={onClear}>
          Clear
        </button>
      </div>
      <pre className="readout small">{output}</pre>
    </section>
  );
}
