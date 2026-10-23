import { useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ask } from "../api.js";

const SHOW_ROWS = 50;
const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const fmt = (v) => (v === null ? "–" : isNum(v) ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : String(v));
const pretty = (c) => c.replace(/_/g, " ");

// Pick a chart only when it helps: one label column + one numeric column, 2-30 rows
function chartFor(columns, rows) {
  if (rows.length < 2 || rows.length > 30 || columns.length < 2) return null;
  const numeric = columns.map((_, i) => rows.every((r) => r[i] === null || isNum(r[i])));
  const label = numeric.findIndex((n) => !n);
  const labelIdx = label === -1 ? 0 : label;
  const candidates = columns.map((c, i) => i).filter((i) => i !== labelIdx && numeric[i]);
  if (!candidates.length) return null;
  const pref = candidates.find((i) => /pct|rate|share|avg|score|days|value|revenue/i.test(columns[i]));
  const valueIdx = pref ?? candidates[candidates.length - 1];
  const data = rows.map((r) => ({ label: String(r[labelIdx]), value: r[valueIdx] }));
  const timeLike = /month|year|date/i.test(columns[labelIdx]) || /^\d{4}(-\d{2})?/.test(data[0].label);
  return { data, kind: timeLike ? "line" : "bar", name: pretty(columns[valueIdx]), label: pretty(columns[labelIdx]) };
}

function Chart({ chart }) {
  const common = { data: chart.data, margin: { top: 8, right: 16, bottom: 4, left: 0 } };
  const axisColor = "var(--muted)";
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={240}>
        {chart.kind === "line" ? (
          <LineChart {...common}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: axisColor }} tickFormatter={(s) => s.slice(0, 7)} />
            <YAxis tick={{ fontSize: 12, fill: axisColor }} width={48} />
            <Tooltip formatter={(v) => [fmt(v), chart.name]} />
            <Line dataKey="value" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        ) : (
          <BarChart {...common}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: axisColor }} interval={0}
                   angle={chart.data.length > 8 ? -35 : 0} textAnchor={chart.data.length > 8 ? "end" : "middle"}
                   height={chart.data.length > 8 ? 70 : 30} />
            <YAxis tick={{ fontSize: 12, fill: axisColor }} width={48} />
            <Tooltip formatter={(v) => [fmt(v), chart.name]} cursor={{ fill: "var(--mark)" }} />
            <Bar dataKey="value" fill="var(--accent)" radius={[3, 3, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
      <p className="hint">{chart.name} by {chart.label}</p>
    </div>
  );
}

function Result({ turn }) {
  const [showSql, setShowSql] = useState(false);
  const [copied, setCopied] = useState(false);
  const { res, error } = turn;

  if (error) return <div className="reply problem">{error}</div>;
  if (!res) return <div className="reply thinking"><span className="dot" /><span className="dot" /><span className="dot" /> Writing and checking the SQL…</div>;
  if (res.refused) return <div className="reply muted-reply">{res.answer}</div>;
  if (res.error) {
    return (
      <div className="reply problem">
        {res.error.startsWith("Blocked")
          ? "That request was stopped by the safety check. Only read-only questions about the data are allowed."
          : "The query could not be run, even after one automatic fix. Try asking it a different way."}
        {res.sql && <details className="sql-box"><summary>SQL that was rejected</summary><pre>{res.sql}</pre></details>}
      </div>
    );
  }

  const chart = chartFor(res.columns, res.rows);
  const numCol = res.columns.map((_, i) => res.rows.length > 0 && res.rows.every((r) => r[i] === null || isNum(r[i])));
  const copy = () => navigator.clipboard?.writeText(res.sql).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });

  return (
    <div className="reply">
      {res.answer && <p className="answer-text">{res.answer}</p>}
      {chart && <Chart chart={chart} />}
      {res.rows.length > 0 && (
        <div className="table-wrap">
          <table className="grid">
            <thead><tr>{res.columns.map((c, i) => <th key={c} className={numCol[i] ? "r" : ""}>{pretty(c)}</th>)}</tr></thead>
            <tbody>
              {res.rows.slice(0, SHOW_ROWS).map((r, i) => (
                <tr key={i}>{r.map((v, j) => <td key={j} className={isNum(v) ? "r" : ""}>{fmt(v)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="meta">
        <span>{res.rows.length > SHOW_ROWS ? `showing ${SHOW_ROWS} of ${res.rows.length} rows` : `${res.rows.length} row${res.rows.length === 1 ? "" : "s"}`}</span>
        <span>{res.seconds.toFixed(1)} s</span>
        {res.repaired && <span title="The first query had an error; the model fixed it once.">fixed itself once</span>}
        <button className="link" onClick={() => setShowSql(!showSql)}>{showSql ? "Hide SQL" : "Show SQL"}</button>
      </div>
      {showSql && (
        <div className="sql-box">
          <button className="copy" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
          <pre>{res.sql}</pre>
        </div>
      )}
    </div>
  );
}

export default function Ask({ examples, turns, setTurns }) {
  const [text, setText] = useState("");
  const busy = turns.some((t) => !t.res && !t.error);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length]);

  const send = async (q) => {
    const question = (q ?? text).trim();
    if (question.length < 3 || busy) return;
    setText("");
    const id = Date.now();
    setTurns((t) => [...t, { id, question }]);
    try {
      const res = await ask(question);
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, res } : x)));
    } catch (e) {
      const msg = /fetch/i.test(e.message)
        ? "Couldn't reach the server. It may be starting up; try again in a few seconds."
        : e.message;
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: msg } : x)));
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="ask">
      {turns.length === 0 && (
        <div className="welcome">
          <h2>Ask the delivery data a question</h2>
          <p className="intro">
            96,018 delivered orders from a Brazilian online marketplace (2017 – 2018): delivery times, late orders,
            sellers, products, payments and reviews. Type a question in plain English. You get the answer, the table,
            and the SQL that produced it, so every number can be checked.
          </p>
        </div>
      )}

      <div className="thread">
        {turns.map((t) => (
          <div key={t.id} className="turn">
            <div className="q">{t.question}</div>
            <Result turn={t} />
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {examples.length > 0 && (
        <div className="chips">
          <span className="hint">Try:</span>
          {examples.slice(0, turns.length ? 4 : 8).map((ex) => (
            <button key={ex} className="chip" disabled={busy} onClick={() => send(ex)}>{ex}</button>
          ))}
        </div>
      )}

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea rows={2} maxLength={300} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKey}
                  placeholder="e.g. Which 5 sellers with 100+ orders are late most often?" aria-label="Your question" />
        <button type="submit" disabled={busy || text.trim().length < 3}>{busy ? "Working…" : "Ask"}</button>
      </form>
      <p className="hint small">Read-only: questions that try to change data are refused. Enter to send, Shift + Enter for a new line.</p>
    </div>
  );
}
