export default function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="space-y-2">
      <p
        className="text-[11px] font-semibold uppercase tracking-[0.24em]"
        style={{ color: "var(--accent)" }}
      >
        {eyebrow}
      </p>
      <div className="space-y-1">
        <h2 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>
          {title}
        </h2>
        {description && (
          <p className="max-w-3xl text-sm leading-6" style={{ color: "var(--text-dim)" }}>
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
