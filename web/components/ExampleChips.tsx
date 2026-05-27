"use client";

export const EXAMPLE_QUESTIONS: readonly string[] = [
  "What does Apple list as its principal competitive factors?",
  "Compare Tesla and NVIDIA risk factors related to supply chain",
  "How does NVIDIA describe export controls on AI chips?",
  "What was the GDP of France in 2023?",
];

interface Props {
  onPick: (question: string) => void;
  disabled?: boolean;
}

export default function ExampleChips({ onPick, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {EXAMPLE_QUESTIONS.map((q) => (
        <button
          key={q}
          type="button"
          disabled={disabled}
          onClick={() => onPick(q)}
          className="rounded-full border border-border bg-surface px-3 py-1.5 text-left text-xs text-text/90 transition hover:border-accent/60 hover:bg-surface-2 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
