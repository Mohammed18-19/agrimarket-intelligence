'use client';

import { useEffect, useState } from 'react';
import DashboardSections from './components/DashboardSections';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Activity, BarChart3, Bell, BrainCircuit, CheckCircle2,
  ChevronRight, Circle, CloudSun, Database, FileText, Globe2,
  Leaf, LoaderCircle, Play, ShieldCheck, Sprout, Sun,
  TrendingUp, Wheat, Workflow, Settings, Moon, Search,
  Copy, AlertTriangle, BookOpenCheck, CheckCircle2 as CheckIcon
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
  const [answerData, setAnswerData] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState('');
  const [activeNav, setActiveNav] = useState('Investigation Workspace');

  const [productionHistory, setProductionHistory] = useState<Record<string, any>[]>([]);
  const [productionLoading, setProductionLoading] = useState(true);
  const [productionError, setProductionError] = useState('');

  const [climateRecords, setClimateRecords] = useState<Record<string, any>[]>([]);
  const [climateLocations, setClimateLocations] = useState<string[]>([]);
  const [climateLocation, setClimateLocation] = useState('Kenitra');
  const [climateLoading, setClimateLoading] = useState(true);
  const [climateError, setClimateError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadProduction() {
      setProductionLoading(true);
      setProductionError('');

      try {
        const response = await fetch(
          `/api/crops/${encodeURIComponent(crop)}/history`
        );
        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload.error || `HTTP ${response.status}`);
        }

        if (!cancelled) {
          setProductionHistory(
            Array.isArray(payload.history) ? payload.history : []
          );
        }
      } catch (error) {
        if (!cancelled) {
          setProductionHistory([]);
          setProductionError(
            error instanceof Error ? error.message : 'Could not load production data.'
          );
        }
      } finally {
        if (!cancelled) setProductionLoading(false);
      }
    }

    void loadProduction();
    return () => { cancelled = true; };
  }, [crop]);

  useEffect(() => {
    let cancelled = false;

    async function loadClimate() {
      setClimateLoading(true);
      setClimateError('');

      try {
        const response = await fetch('/api/climate');
        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload.error || `HTTP ${response.status}`);
        }

        if (!cancelled) {
          const records = Array.isArray(payload.records) ? payload.records : [];
          const locations = Array.isArray(payload.locations) ? payload.locations : [];

          setClimateRecords(records);
          setClimateLocations(locations);

          if (locations.length && !locations.includes(climateLocation)) {
            setClimateLocation(
              locations.includes('Kenitra') ? 'Kenitra' : locations[0]
            );
          }
        }
      } catch (error) {
        if (!cancelled) {
          setClimateRecords([]);
          setClimateError(
            error instanceof Error ? error.message : 'Could not load climate data.'
          );
        }
      } finally {
        if (!cancelled) setClimateLoading(false);
      }
    }

    void loadClimate();
    return () => { cancelled = true; };
  }, []);

  async function runInvestigation() {
    if (!question.trim() || running) return;

    setRunning(true);
    setEvents([]);
    setAnswer('');
    setAnswerData(null);
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
          setAnswerData(result);
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
              {answerData ? (
                <div className="final-report">
                  <div className="report-banner">
                    <div className="report-banner-icon"><Sprout size={23} /></div>
                    <div className="report-banner-copy">
                      <span className="report-eyebrow">AGRICULTURAL INTELLIGENCE</span>
                      <h3>Investigation Report</h3>
                      <p>{answerData.question || question}</p>
                    </div>
                    <span className="report-complete"><CheckIcon size={14} /> Received</span>
                  </div>

                  <div className="report-section">
                    <div className="report-section-title">
                      <span className="report-section-icon summary-icon"><FileText size={17} /></span>
                      <h3>Executive Analysis</h3>
                    </div>
                    <div className="report-analysis markdown-report">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: ({ children }) => <h2 className="md-report-title">{children}</h2>,
                          h2: ({ children }) => <h3 className="md-report-heading">{children}</h3>,
                          h3: ({ children }) => <h4 className="md-report-subheading">{children}</h4>,
                          p: ({ children }) => <p>{children}</p>,
                          table: ({ children }) => (
                            <div className="md-table-wrap">
                              <table className="md-report-table">{children}</table>
                            </div>
                          ),
                          thead: ({ children }) => <thead>{children}</thead>,
                          th: ({ children }) => <th>{children}</th>,
                          td: ({ children }) => <td>{children}</td>,
                          blockquote: ({ children }) => (
                            <blockquote className="md-report-callout">{children}</blockquote>
                          ),
                          ul: ({ children }) => <ul className="md-report-list">{children}</ul>,
                          ol: ({ children }) => <ol className="md-report-list md-report-ordered">{children}</ol>,
                          li: ({ children }) => <li>{children}</li>,
                          strong: ({ children }) => <strong>{children}</strong>,
                          a: ({ href, children }) => (
                            <a href={href} target="_blank" rel="noreferrer">{children}</a>
                          ),
                          hr: () => <hr className="md-report-divider" />,
                        }}
                      >
                        {String(answerData.analysis || 'No analysis text was returned.')}
                      </ReactMarkdown>
                    </div>
                  </div>

                  <div className="report-section">
                    <div className="report-section-title">
                      <span className="report-section-icon evidence-icon"><Database size={17} /></span>
                      <h3>Retrieved Evidence</h3>
                      <span className="report-count">
                        {Object.keys(answerData.evidence || {}).length} sources
                      </span>
                    </div>
                    {Object.entries(answerData.evidence || {}).length ? (
                      <div className="evidence-list">
                        {Object.entries(answerData.evidence || {}).map(([key, value]: [string, any]) => {
                          const failed = value?.status === 'error' || value?.status === 'failed';
                          return (
                            <details className="evidence-card" key={key}>
                              <summary>
                                <span className={`evidence-status ${failed ? 'evidence-status-error' : ''}`}>
                                  {failed ? <AlertTriangle size={15} /> : <CheckIcon size={15} />}
                                </span>
                                <span className="evidence-name">
                                  {key.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                  <small>{value?.agent || 'Investigation evidence'}</small>
                                </span>
                                <span className="evidence-expand">View details</span>
                              </summary>
                              <pre className="evidence-json">{JSON.stringify(value, null, 2)}</pre>
                            </details>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="report-muted">No evidence payload was returned for this investigation.</p>
                    )}
                  </div>

                  <div className="report-section">
                    <div className="report-section-title">
                      <span className="report-section-icon validation-icon"><ShieldCheck size={17} /></span>
                      <h3>Evidence Validation</h3>
                    </div>
                    <div className="validation-card">
                      <div className="validation-heading">
                        <ShieldCheck size={18} />
                        <strong>
                          {String(answerData.validation?.status || 'Validation details available')}
                            .replace(/[_-]/g, ' ')
                        </strong>
                      </div>
                      <pre className="evidence-json">
                        {JSON.stringify(answerData.validation || { message: 'No validation details returned.' }, null, 2)}
                      </pre>
                      <p>Validation checks data availability and structure; it does not guarantee that every interpretation is correct.</p>
                    </div>
                  </div>

                  {answerData.note && (
                    <div className="report-note">
                      <AlertTriangle size={17} />
                      <div><strong>Interpretation note</strong><p>{answerData.note}</p></div>
                    </div>
                  )}

                  <div className="report-actions">
                    <button className="report-copy-button" onClick={() => {
                      void navigator.clipboard.writeText(answer)
                        .then(() => window.alert('Report copied to clipboard.'))
                        .catch(() => window.alert('Copy failed. Please select and copy the report text.'));
                    }}>
                      <Copy size={16} /> Copy full report
                    </button>
                    <button className="report-export-button" onClick={() => {
                      const blob = new Blob([JSON.stringify(answerData, null, 2)], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const link = document.createElement('a');
                      link.href = url;
                      link.download = 'agrimarket-investigation-report.json';
                      link.click();
                      URL.revokeObjectURL(url);
                    }}>
                      <BookOpenCheck size={16} /> Export JSON
                    </button>
                  </div>
                </div>
              ) : (
                <div className="answer-placeholder"><BrainCircuit size={29} /><strong>Your analysis will appear here</strong><p>Run an investigation to display the response returned by the backend.</p></div>
              )}
              <div className="metric-grid">
                <div className="metric-card growth"><Sprout size={17} /><span>Production data</span><strong>On demand</strong><small>From project datasets</small></div>
                <div className="metric-card risk"><CloudSun size={17} /><span>Climate analysis</span><strong>On demand</strong><small>Source-dependent</small></div>
                <div className="metric-card confidence"><ShieldCheck size={17} /><span>Evidence checks</span><strong>Required</strong><small>Report limitations</small></div>
              </div>
            </section>

            <section className="viz-section">
              <h2><BarChart3 size={18} /> Key Visualizations</h2>
              <div className="viz-grid">
                <div className="panel viz-card">
                  <strong>{crop} Production</strong>
                  <span>Annual observations · tonnes (t)</span>

                  {productionLoading ? (
                    <p className="chart-state">Loading production history…</p>
                  ) : productionError ? (
                    <p className="chart-state chart-error">Production data unavailable: {productionError}</p>
                  ) : productionHistory.length === 0 ? (
                    <p className="chart-state">No historical observations available for {crop}.</p>
                  ) : (
                    <>
                      <div className="bar-chart data-bars">
                        {productionHistory.map((record, index) => {
                          const value = Number(record.Value);
                          const maxValue = Math.max(
                            ...productionHistory.map(row => Number(row.Value) || 0),
                            1
                          );

                          return (
                            <div className="data-bar" key={`${record.Year}-${index}`}>
                              <i
                                title={`${record.Year}: ${Number.isFinite(value) ? value.toLocaleString() : 'Unavailable'} ${record.Unit || 't'}`}
                                style={{
                                  height: `${Number.isFinite(value) && value >= 0 ? Math.max(3, value / maxValue * 100) : 0}%`,
                                  visibility: Number.isFinite(value) && value >= 0 ? 'visible' : 'hidden',
                                }}
                              />
                              <small>{String(record.Year ?? '').slice(-2)}</small>
                            </div>
                          );
                        })}
                      </div>
                      <div className="chart-foot">
                        <span>{productionHistory[0]?.Year}</span>
                        <span>
                          Latest: {productionHistory[productionHistory.length - 1]?.Year}
                        </span>
                      </div>
                      <p className="chart-note">
                        Bars are scaled relative to the largest displayed annual value. Hover over a bar for its value.
                      </p>
                    </>
                  )}
                </div>

                <div className="panel viz-card">
                  <strong>Climate Indicators</strong>
                  <span>Mean annual temperature · °C</span>

                  <label className="climate-select-label" htmlFor="climate-location">
                    Location
                  </label>
                  <select
                    id="climate-location"
                    className="climate-location-select"
                    value={climateLocation}
                    onChange={event => setClimateLocation(event.target.value)}
                    disabled={climateLoading || climateLocations.length === 0}
                  >
                    {climateLocations.map(location => (
                      <option key={location} value={location}>{location}</option>
                    ))}
                  </select>

                  {climateLoading ? (
                    <p className="chart-state">Loading climate observations…</p>
                  ) : climateError ? (
                    <p className="chart-state chart-error">Climate data unavailable: {climateError}</p>
                  ) : climateRecords.filter(
                    record => record.location === climateLocation &&
                      Number.isFinite(Number(record.mean_temperature_c))
                  ).length === 0 ? (
                    <p className="chart-state">
                      No temperature observations available for {climateLocation}.
                    </p>
                  ) : (
                    <>
                      <div className="bar-chart data-bars">
                        {climateRecords
                          .filter(record =>
                            record.location === climateLocation &&
                            Number.isFinite(Number(record.mean_temperature_c))
                          )
                          .sort((a, b) => Number(a.year) - Number(b.year))
                          .map((record, index, records) => {
                            const value = Number(record.mean_temperature_c);
                            const minValue = Math.min(...records.map(row => Number(row.mean_temperature_c)));
                            const maxValue = Math.max(...records.map(row => Number(row.mean_temperature_c)));
                            const range = maxValue - minValue;

                            return (
                              <div className="data-bar" key={`${record.year}-${index}`}>
                                <i
                                  title={`${record.location}, ${record.year}: ${value.toFixed(2)} °C`}
                                  style={{
                                    height: `${range === 0 ? 100 : 8 + ((value - minValue) / range) * 92}%`,
                                  }}
                                />
                                <small>{String(record.year).slice(-2)}</small>
                              </div>
                            );
                          })}
                      </div>
                      <div className="chart-foot">
                        <span>Lower bar = cooler year</span>
                        <span>Higher bar = warmer year</span>
                      </div>
                      <p className="chart-note">
                        Bar heights show relative temperatures within this location's available years, not a common scale across locations.
                      </p>
                    </>
                  )}
                </div>
              </div>
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
