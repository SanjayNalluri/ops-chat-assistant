export default function About() {
  return (
    <div className="panel narrow about">
      <h2>About Ops Chat</h2>
      <p>
        Operations teams often wait for an analyst to answer simple questions about their own data. Ops Chat lets
        anyone ask in plain English and still see exactly how each number was calculated.
      </p>

      <h3>How a question is answered</h3>
      <ol>
        <li><b>Write SQL.</b> A language model (Groq, gpt-oss-120b) gets the question, plain notes on every table
          and column, and three worked examples, and writes one SQLite query.</li>
        <li><b>Check it.</b> The query is parsed before it runs. Only a single SELECT on the 9 known tables is
          allowed: no changes, no system tables, no file functions. Results are capped at 500 rows.</li>
        <li><b>Run it safely.</b> The database file is opened read-only with a 5-second limit. If the query has a
          simple mistake, the model gets the error and one chance to fix it.</li>
        <li><b>Explain it.</b> A one or two sentence answer is written only from the rows that came back, next to the
          table, a chart when it helps, and the SQL.</li>
      </ol>

      <h3>The data</h3>
      <p>
        Olist Brazilian e-commerce orders (Kaggle, CC BY-NC-SA 4.0), cleaned in SQL Server for the{" "}
        <a href="https://github.com/SanjayNalluri/deliverylens-delivery-analytics">DeliveryLens</a> project and copied
        to SQLite so it can ship with the API. Order, customer and seller IDs are replaced by numbers.
      </p>

      <h3>Built with</h3>
      <p className="muted">Python, FastAPI, sqlglot, SQLite, SQL Server · Groq LLM API · pytest, GitHub Actions ·
        React, Recharts · Vercel</p>
    </div>
  );
}
