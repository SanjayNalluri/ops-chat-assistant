const pct = (n, d) => `${Math.round((1000 * n) / d) / 10}%`;

export default function Accuracy({ evaluation }) {
  if (!evaluation) return <div className="msg">Loading the test results…</div>;
  const runs = evaluation.runs;
  const v2 = runs[runs.length - 1];
  const hold = evaluation.holdout;
  const head = hold || v2;
  const att = evaluation.attacks;
  const stopped = att ? att.total - (att.outcomes["UNSAFE QUERY RAN"] || 0) : null;

  return (
    <div className="stack">
      <div>
        <h2>How accurate is it?</h2>
        <p className="intro">
          Before trusting a number, test the tool. Questions were answered with SQL written by hand; the assistant
          answered the same questions, and its result table was compared with the hand-written one.
          {hold ? " The headline numbers come from 60 held-out questions that were written before the run and never used to tune the assistant." : ""}
          {" "}Model: <code>{evaluation.model}</code>.
        </p>
      </div>

      <div className="stats">
        <div><b>{head.strict_pct}%</b><span>exactly right ({head.strict} of {head.questions}){hold ? ", held-out set" : ""}</span></div>
        <div><b>{head.lenient_pct}%</b><span>right, allowing different row labels</span></div>
        {att && <div><b>{stopped} / {att.total}</b><span>attempts to change or leak data stopped</span></div>}
        <div><b>{head.median_seconds} s</b><span>median time per question</span></div>
      </div>

      <div className="panel">
        <h3>Results by run</h3>
        <table className="grid">
          <thead>
            <tr><th>Run</th><th>Questions</th><th className="r">Easy</th><th className="r">Medium</th>
                <th className="r">Hard</th><th className="r">Exactly right</th><th className="r">Labels allowed</th></tr>
          </thead>
          <tbody>
            {[...runs, ...(hold ? [hold] : [])].map((r) => (
              <tr key={r.run} className={r === head ? "mark" : ""}>
                <td>{r.run}</td>
                <td className="muted-cell">{r.run === "holdout" ? "60 held-out" : "40 development"}: {r.note}</td>
                {r.by_difficulty.map((d) => <td key={d.difficulty} className="r">{d.strict}/{d.questions}</td>)}
                <td className="r">{r.strict_pct}%</td>
                <td className="r">{r.lenient_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint pad">
          "Labels allowed" also counts answers whose numbers are right but whose row names differ, e.g. "Late / On-time"
          instead of 1 / 0. The notes added before run v2 were written after seeing run v1's mistakes, so v2 is not an
          independent test{hold ? "; the held-out run is" : ""}.
        </p>
      </div>

      {hold?.by_category && (
        <div className="panel">
          <h3>Held-out results by question type</h3>
          <table className="grid">
            <thead><tr><th>Type</th><th className="r">Questions</th><th className="r">Exactly right</th><th className="r">Labels allowed</th></tr></thead>
            <tbody>
              {hold.by_category.map((c) => (
                <tr key={c.category}>
                  <td>{c.category}</td><td className="r">{c.questions}</td>
                  <td className="r">{pct(c.strict, c.questions)}</td><td className="r">{pct(c.lenient, c.questions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {hold.wrong.length > 0 && (
            <>
              <h3 style={{ marginTop: 16 }}>Held-out questions it got wrong</h3>
              <ul className="plain">{hold.wrong.map((w) => <li key={w.id}>{w.id}: {w.question}</li>)}</ul>
            </>
          )}
        </div>
      )}

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
            <h3>Attempts to change or leak data ({att.total})</h3>
            <ul>
              {att.list.map((a) => {
                const kind = a.outcome.startsWith("blocked") ? ["tag-guard", "safety check"]
                  : a.outcome.startsWith("stopped") ? ["tag-guard", "time limit"]
                  : a.outcome.startsWith("model") ? ["tag-model", "model refused"] : ["tag-model", "read-only query"];
                return <li key={a.prompt}><span className={`tag ${kind[0]}`}>{kind[1]}</span>{a.prompt}</li>;
              })}
            </ul>
            <p className="hint">Even if every other layer failed, the database file is opened read-only.</p>
          </div>
        )}
      </div>
    </div>
  );
}
