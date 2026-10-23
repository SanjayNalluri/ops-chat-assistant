export default function Accuracy({ evaluation }) {
  if (!evaluation) return <div className="msg">Loading the test results…</div>;
  const runs = evaluation.runs;
  const last = runs[runs.length - 1];
  const att = evaluation.attacks;
  const stopped = att ? att.total - (att.outcomes["UNSAFE QUERY RAN"] || 0) : null;

  return (
    <div className="stack">
      <div>
        <h2>How accurate is it?</h2>
        <p className="intro">
          Before trusting a number, test the tool. 40 questions (12 easy, 14 medium, 14 hard) were answered with SQL
          written by hand. The assistant answered the same questions, and its result table was compared with the
          hand-written one. Model: <code>{evaluation.model}</code>.
        </p>
      </div>

      <div className="stats">
        <div><b>{last.strict_pct}%</b><span>exactly right ({last.strict} of 40)</span></div>
        <div><b>{last.lenient_pct}%</b><span>right, allowing different row labels</span></div>
        {att && <div><b>{stopped} / {att.total}</b><span>attempts to change data stopped</span></div>}
        <div><b>{last.median_seconds} s</b><span>median time per question</span></div>
      </div>

      <div className="panel">
        <h3>Results by run</h3>
        <table className="grid">
          <thead>
            <tr><th>Run</th><th>What changed</th><th className="r">Easy</th><th className="r">Medium</th>
                <th className="r">Hard</th><th className="r">Exactly right</th><th className="r">Labels allowed</th></tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run} className={r === last ? "mark" : ""}>
                <td>{r.run}</td>
                <td className="muted-cell">{r.note}</td>
                {r.by_difficulty.map((d) => <td key={d.difficulty} className="r">{d.strict}/{d.questions}</td>)}
                <td className="r">{r.strict_pct}%</td>
                <td className="r">{r.lenient_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint pad">
          "Labels allowed" also counts answers whose numbers are right but whose row names differ, e.g. "Late / On-time"
          instead of 1 / 0. The notes added before run v2 were written after seeing run v1's mistakes, so v2 is not a
          fully independent test.
        </p>
      </div>

      <div className="two">
        <div className="panel takeaways">
          <h3>What went wrong in run v1</h3>
          <ul>
            {runs[0].wrong.map((w) => <li key={w.id}>Q{w.id}: {w.question}</li>)}
          </ul>
          <p className="hint">Fixed in v2 by noting how customers join to orders, that "month" means purchase month,
            and that items must be de-duplicated before averaging by category.</p>
        </div>

        {att && (
          <div className="panel takeaways">
            <h3>Attempts to change or leak data</h3>
            <ul>
              {att.list.map((a) => (
                <li key={a.prompt}>
                  <span className={`tag ${a.outcome.startsWith("blocked") ? "tag-guard" : "tag-model"}`}>
                    {a.outcome.startsWith("blocked") ? "safety check" : "model refused"}
                  </span>
                  {a.prompt}
                </li>
              ))}
            </ul>
            <p className="hint">Even if both layers failed, the database file is opened read-only.</p>
          </div>
        )}
      </div>
    </div>
  );
}
