'use client';

import { useState } from 'react';
import DashboardSections from './components/DashboardSections';
import {
  Activity, BarChart3, Bell, BrainCircuit, CheckCircle2,
  ChevronRight, Circle, CloudSun, Database, FileText, Globe2,
  Leaf, LoaderCircle, Play, ShieldCheck, Sprout, Sun,
  TrendingUp, Wheat, Workflow, Settings, Moon, Search
} from 'lucide-react';

const agents = [
  { name: 'Supervisor', desc: 'Planning investigation strategy', icon: BrainCircuit },
  { name: 'Data Investigation', desc: 'Querying production and climate tools', icon: Database },
  { name: 'Analysis Specialists', desc: 'Analyzing trends and forecast reliability', icon: TrendingUp },
  { name: 'Evidence Verification', desc: 'Checking sources and limitations', icon: ShieldCheck },
];

const sources = [
  { name: 'FAOSTAT · Wheat Production', desc: 'Morocco · Historical production data', icon: Wheat },
  { name: 'NASA POWER · Climate Data', desc: 'Daily climate observations · 5 locations', icon: CloudSun },
  { name: 'Forecast Evaluation', desc: 'Naive baseline vs. linear trend', icon: BarChart3 },
];

const nav = [
  { label: 'Investigation Workspace', icon: Workflow },
  { label: 'Production Analytics', icon: Wheat },
  { label: 'Climate Risk', icon: CloudSun },
  { label: 'Forecasting', icon: TrendingUp },
  { label: 'Crop Suitability', icon: Sprout },
  { label: 'Global Insights', icon: Globe2 },
  { label: 'Reports', icon: FileText },
  { label: 'Data Sources', icon: Database },
];

export default function Home() {
  const [question, setQuestion] = useState(
    'Analyze wheat production trends and climate risks in Morocco, and explain the reliability of the forecast.'
  );
  const [crop, setCrop] = useState('Wheat');
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<Record<string, any>[]>([]);
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState('');
  const [activeNav, setActiveNav] = useState('Investigation Workspace');

  async function runInvestigation() {
    if (!question.trim() || running) return;

    setRunning(true);
    setEvents([]);
    setAnswer('');
    setError('');

    try {
      const response = await fetch('/api/ai/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, crop, location: 'Morocco' }),
      });

      if (!response.ok || !response.body) {
        const message = await response.text().catch(() => '');
        let detail = message;

        try {
          const parsed = JSON.parse(message);
          detail = parsed.error ?? message;
        } catch {}

        throw new Error(
          detail || `Workflow request failed (${response.status}).`
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let receivedFinal = false;
      let streamError = '';

      function processChunk(chunk: string) {
        let eventType = '';
        const data = chunk
          .split(/\r?\n/)
          .filter(line => {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            }
            return line.startsWith('data:');
          })
          .map(line => line.slice(5).trimStart())
          .join('\n');

        if (!data || data === '[DONE]') return;

        let event: Record<string, any>;

        try {
          event = JSON.parse(data);
        } catch {
          setEvents(previous => [
            ...previous,
            { type: 'message', message: data },
          ]);
          return;
        }

        if (eventType === 'error') event.type = 'error';
        setEvents(previous => [...previous, event]);

        if (event.type === 'error' || event.error) {
          streamError =
            typeof event.error === 'string'
              ? event.error
              : 'The agricultural workflow failed. Check the backend logs.';
          setError(streamError);
          return;
        }

        if (event.type === 'final' && event.answer) {
          receivedFinal = true;
          const result = event.answer;
          const sections = [
            typeof result.analysis === 'string' ? result.analysis : '',
            result.validation
              ? `EVIDENCE VALIDATION\n${JSON.stringify(result.validation, null, 2)}`
              : '',
            result.evidence
              ? `RETRIEVED EVIDENCE\n${JSON.stringify(result.evidence, null, 2)}`
              : '',
            result.note ? `NOTE\n${result.note}` : '',
          ].filter(Boolean);

          setAnswer(
            sections.join('\n\n') ||
              'The workflow completed but returned no analysis text.'
          );
        }
      }

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split(/\r?\n\r?\n/);
        buffer = chunks.pop() ?? '';

        for (const chunk of chunks) processChunk(chunk);
      }

      buffer += decoder.decode();
      if (buffer.trim()) processChunk(buffer);

      if (!receivedFinal && !streamError) {
        setError(
          'The stream ended without a final answer. Check the Flask API logs.'
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown workflow error');
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="agent-os">
      <aside className="agent-sidebar">
        <div className="brand">
          <div className="brand-icon"><Leaf size={28} fill="currentColor" /></div>
          <div><strong>AgriMarket AI</strong><span>AGENTIC AGRICULTURAL INTELLIGENCE</span></div>
        </div>

        <div className="nav-list">
          {nav.map(({ label, icon: Icon }) => (
            <button key={label} onClick={() => setActiveNav(label)}
              className={`nav-item ${activeNav === label ? 'selected' : ''}`}>
              <Icon size={18} /><span>{label}</span>
              {label === 'Reports' && <i className="nav-dot" />}
            </button>
          ))}
        </div>

        <div className="sidebar-bottom">
          <div className="powered-card">
            <div className="powered-icon"><Workflow size={22} /></div>
            <div><strong>Powered by LangGraph</strong><p>Multi-step research · Real data · Evidence-based answers</p></div>
          </div>
          <div className="profile">
            <div className="avatar">M</div>
            <div><strong>Mohammed Ain Tomar</strong><span>Student · AI Engineer</span></div>
            <Settings size={18} />
          </div>
        </div>
      </aside>

      <section className="agent-main">
        <header className="topbar">
          <Leaf size={19} fill="currentColor" />
          <div className="topbar-right"><Sun size={19} /><Bell size={19} /><div className="avatar small">M</div></div>
        </header>

        {activeNav === 'Investigation Workspace' ? (
        <div className="workspace">
          <section className="center-column">
            <div className="eyebrow"><SparkleIcon /> NEW INVESTIGATION</div>
            <h1>What should we investigate today?</h1>
            <p className="intro">Ask a question. The agent supervisor will plan the investigation, invoke relevant tools, and assemble an evidence-backed answer.</p>

            <div className="command-card">
              <textarea value={question} onChange={e => setQuestion(e.target.value)}
                aria-label="Investigation question" placeholder="Ask about agricultural production, climate risks, or forecast reliability..." />
              <div className="command-bottom">
                <div className="selectors">
                  <label><Wheat size={14} /><select value={crop} onChange={e => setCrop(e.target.value)}>
                    {['Wheat', 'Barley', 'Maize', 'Tomatoes', 'Potatoes', 'Olives', 'Citrus'].map(c => <option key={c}>{c}</option>)}
                  </select></label>
                  <span className="selector-pill"><Globe2 size={14} /> Region: Morocco</span>
                </div>
                <button className="run-button" onClick={runInvestigation} disabled={running}>
                  {running ? <LoaderCircle size={16} className="spin" /> : <Play size={15} fill="currentColor" />}
                  {running ? 'Investigating…' : 'Run Investigation'}
                </button>
              </div>
            </div>

            <section className="panel execution-panel">
              <div className="panel-heading">
                <h2><Workflow size={19} /> Agent Execution</h2>
                <span className={`status-pill ${running ? 'running' : ''}`}><i />{running ? 'Running' : events.length ? 'Finished' : 'Ready'}</span>
                <span className="live-label"><Activity size={14} /> Live · LangGraph</span>
              </div>
              <div className="agent-timeline">
                {agents.map(({ name, desc, icon: Icon }, i) => {
                  const hasEvent = events.length > 0;
                  const state = !hasEvent ? 'Waiting for run' :
                    (i === 0 ? 'Event received' : 'Awaiting event');
                  return <div className="agent-step" key={name}>
                    <div className={`timeline-icon tone-${i}`}><Icon size={23} /></div>
                    <div className="step-copy"><strong>{i + 1}. {name}</strong><span>{desc}</span></div>
                    <span className={`step-status ${running && i === 1 ? 'blue' : ''}`}>
                      {running && i === 1 ? <LoaderCircle size={12} className="spin" /> :
                        hasEvent && i === 0 ? <CheckCircle2 size={13} /> : <Circle size={12} />}
                      {hasEvent && i === 0 ? 'Event received' : state}
                    </span>
                  </div>;
                })}
              </div>
              <p className="disclaimer">Stage labels describe the workflow design. Only events returned by the server are evidence that a stage executed.</p>
            </section>

            <section className="panel tool-panel">
              <div className="panel-heading"><h2><Activity size={18} /> Live Tool Calls</h2><span className="count-pill">{events.length} events</span></div>
              {events.length === 0 ? (
                <div className="empty-tools"><Database size={20} /><span>Tool calls and workflow events will appear here when an investigation runs.</span></div>
              ) : (
                <div className="event-list">
                  {events.map((event, i) => <div className="event-row" key={i}>
                    <i className="event-dot" /><div className="event-copy"><strong>{String(event.node ?? event.name ?? event.type ?? event.event ?? 'Workflow event')}</strong>
                    <span>{String(event.message ?? event.tool ?? event.status ?? JSON.stringify(event))}</span></div>
                    <span className="event-time">{new Date().toLocaleTimeString()}</span>
                  </div>)}
                </div>
              )}
              {error && <div className="error-box">{error}</div>}
            </section>
          </section>

          <aside className="right-column">
            <div className="ready-row"><span className="ready-dot" />{running ? 'Investigation running' : 'Agent Ready'}</div>
            <section className="panel answer-panel">
              <div className="panel-heading"><h2><FileText size={19} /> Final Answer</h2><span className="status-pill">{answer ? 'Response received' : 'Awaiting run'}</span></div>
              {answer ? <pre className="answer-text">{answer}</pre> :
                <div className="answer-placeholder"><BrainCircuit size={29} /><strong>Your analysis will appear here</strong><p>Run an investigation to display the response returned by the backend.</p></div>}
              <div className="metric-grid">
                <div className="metric-card growth"><Sprout size={17} /><span>Production data</span><strong>On demand</strong><small>From project datasets</small></div>
                <div className="metric-card risk"><CloudSun size={17} /><span>Climate analysis</span><strong>On demand</strong><small>Source-dependent</small></div>
                <div className="metric-card confidence"><ShieldCheck size={17} /><span>Evidence checks</span><strong>Required</strong><small>Report limitations</small></div>
              </div>
            </section>

            <section className="viz-section">
              <h2><BarChart3 size={18} /> Key Visualizations</h2>
              <div className="viz-grid">
                <div className="panel viz-card"><strong>{crop} Production</strong><span>Historical dataset</span>
                  <div className="mini-chart"><svg viewBox="0 0 240 100" preserveAspectRatio="none"><defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#25d895" stopOpacity=".35"/><stop offset="100%" stopColor="#25d895" stopOpacity="0"/></linearGradient></defs><path d="M0,78 L25,67 L50,70 L75,57 L100,60 L125,44 L150,50 L175,30 L200,35 L240,12 L240,100 L0,100Z" fill="url(#area)"/><path d="M0,78 L25,67 L50,70 L75,57 L100,60 L125,44 L150,50 L175,30 L200,35 L240,12" fill="none" stroke="#35e6a0" strokeWidth="2.5"/></svg></div>
                  <div className="chart-foot"><span>Historical</span><span>Latest</span></div>
                </div>
                <div className="panel viz-card"><strong>Climate Indicators</strong><span>Annual comparison</span>
                  <div className="bar-chart">{[28,38,32,51,44,64,56,74,66,88].map((n,i)=><i key={i} style={{height:`${n}%`}} />)}</div>
                  <div className="chart-foot"><span>Earlier</span><span>Recent</span></div>
                </div>
              </div>
              <p className="chart-note">Illustrative chart styling. Connect verified API series before treating chart values as results.</p>
            </section>

            <section className="panel sources-panel">
              <div className="panel-heading"><h2><ShieldCheck size={18} /> Evidence &amp; Sources</h2><span className="source-count">Project sources</span></div>
              {sources.map(({name,desc,icon:Icon})=><div className="source-row" key={name}>
                <div className="source-icon"><Icon size={18}/></div><div className="source-copy"><strong>{name}</strong><span>{desc}</span></div><span className="source-mark"><Database size={12}/> Available</span>
              </div>)}
              <p className="chart-note">Source availability does not mean a source was used in the current answer. Confirm citations from actual workflow output.</p>
            </section>
          </aside>
        </div>
        ) : (
          <DashboardSections section={activeNav} />
        )}
      </section>
    </main>
  );
}

function SparkleIcon() {
  return <Sprout size={14} />;
}
