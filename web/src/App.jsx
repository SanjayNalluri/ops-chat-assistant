import { useEffect, useState } from "react";
import { API, get } from "./api.js";
import Ask from "./pages/Ask.jsx";
import Accuracy from "./pages/Accuracy.jsx";
import About from "./pages/About.jsx";

const TABS = [
  { id: "ask", label: "Ask" },
  { id: "accuracy", label: "How accurate is it?" },
  { id: "about", label: "About" },
];
const GITHUB = "https://github.com/SanjayNalluri/ops-chat-assistant";

const readTab = () => {
  const h = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === h) ? h : "ask";
};

export default function App() {
  const [tab, setTab] = useState(readTab);
  const [examples, setExamples] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [turns, setTurns] = useState([]);           // kept here so switching tabs keeps the chat

  useEffect(() => {
    const onHash = () => setTab(readTab());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    get("/examples").then(setExamples).catch(() => {});
    get("/evaluation").then(setEvaluation).catch(() => {});
  }, []);

  return (
    <>
      <nav className="topbar">
        <div className="wrap topbar-inner">
          <a href="#ask" className="brand">Ops Chat <span>delivery data, plain English</span></a>
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <a key={t.id} href={`#${t.id}`} role="tab" aria-selected={tab === t.id}
                 className={tab === t.id ? "tab active" : "tab"}>{t.label}</a>
            ))}
          </div>
          <a className="gh" href={GITHUB}>GitHub ↗</a>
        </div>
      </nav>

      <main className="wrap">
        {tab === "ask" && <Ask examples={examples} turns={turns} setTurns={setTurns} />}
        {tab === "accuracy" && <Accuracy evaluation={evaluation} />}
        {tab === "about" && <About />}
      </main>

      <footer className="wrap foot">
        Nalluri Sanjay · Industrial &amp; Systems Engineering, IIT Kharagpur ·{" "}
        <a href={GITHUB}>Code</a> · <a href={`${API}/docs`}>API docs</a>
      </footer>
    </>
  );
}
