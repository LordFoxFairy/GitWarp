import { Button } from "@primer/react";

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
        <Button type="button" onClick={onClear}>
          Clear
        </Button>
      </div>
      <pre className="readout small">{output}</pre>
    </section>
  );
}
