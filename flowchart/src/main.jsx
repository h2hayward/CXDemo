import React, { useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, Handle, Position } from '@xyflow/react';
import { toPng } from 'html-to-image';
import '@xyflow/react/dist/style.css';
import './style.css';

function Icon({ name, size = 24 }) {
  const paths = {
    vacancy: <><rect x="5" y="4" width="14" height="17" rx="1" /><path d="M9 4V2h6v2M9 9h6M9 13h6M9 17h4" /></>,
    details: <><path d="m9 7 2 2 4-4M9 15l2 2 4-4M3 8h2M3 16h2M18 8h3M18 16h3" /></>,
    accounts: <><path d="M4 21V7h6M10 21V3h10v18M14 7h2M14 11h2M14 15h2M7 11v1M7 15v1M2 21h20" /></>,
    evidence: <><path d="M5 3h10l4 4v14H5zM14 3v5h5M8 12h8M8 16h6" /></>,
    people: <><circle cx="9" cy="8" r="4" /><path d="M2 21v-2a7 7 0 0 1 12-5M16 16l2 2 4-4" /></>,
    message: <><path d="M21 11a8 8 0 0 1-8 8H6l-4 3V6a4 4 0 0 1 4-4h11a4 4 0 0 1 4 4zM6 7h10M6 11h7" /></>,
    search: <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></>,
    ads: <><rect x="3" y="4" width="18" height="13" rx="1" /><path d="M8 21h8M12 17v4m-2-13 6 3-6 3z" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function CardNode({ data }) {
  return (
    <div className={`flow-card ${data.output ? 'flow-card-output' : ''}`}>
      {data.output && <Handle type="target" position={Position.Left} />}
      <span className="flow-icon"><Icon name={data.icon} /></span>
      <span className="card-copy"><span className="card-label">{data.title}</span><span className="card-meta">{data.meta}</span></span>
      {!data.output && <Handle type="source" position={Position.Right} />}
    </div>
  );
}

const process = [
  ['Read responsibilities', 'search'],
  ['Check active Meta ads', 'ads'],
  ['Find possible owners', 'people'],
  ['Prepare the SDR brief', 'evidence'],
];

function EngineNode() {
  return (
    <div className="flow-engine">
      <div className="engine-header">
        <span className="engine-mark"><img src="/h2-logo.svg" alt="H2" /></span>
        <span>SDR research engine</span>
      </div>
      <div className="engine-steps">
        {process.map(([title, icon], index) => (
          <div className="engine-step" key={title}>
            <span className="step-number">0{index + 1}</span>
            <span>{title}</span>
            <span className="step-icon"><Icon name={icon} size={20} /></span>
          </div>
        ))}
      </div>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { card: CardNode, engine: EngineNode };
const inputs = [
  ['vacancies', 'Job listings', 'Relevant creative hires', 'vacancy'],
  ['details', 'Role details', 'Responsibilities + scope', 'details'],
  ['accounts', 'Account scope', 'Markets + target list', 'accounts'],
];
const outputs = [
  ['evidence', 'Account evidence', 'Why this account', 'evidence'],
  ['contacts', 'Possible contacts', 'Who to speak to', 'people'],
  ['opener', 'Conversation starter', 'A relevant approach', 'message'],
];
const nodes = [
  ...inputs.map(([id, title, meta, icon], i) => ({ id, type: 'card', position: { x: 0, y: 20 + i * 128 }, data: { title, meta, icon }, ariaLabel: `${title}: ${meta}` })),
  { id: 'engine', type: 'engine', position: { x: 400, y: 0 }, data: {}, ariaLabel: 'H2 SDR research engine: read responsibilities, check active Meta ads, find possible owners and prepare the SDR brief.' },
  ...outputs.map(([id, title, meta, icon], i) => ({ id, type: 'card', position: { x: 984, y: 20 + i * 128 }, data: { title, meta, icon, output: true }, ariaLabel: `${title}: ${meta}` })),
];
const edges = [
  ...inputs.map(([id]) => ({ id: `${id}-engine`, source: id, target: 'engine' })),
  ...outputs.map(([id]) => ({ id: `engine-${id}`, source: 'engine', target: id })),
].map(edge => ({ ...edge, type: 'default', style: { stroke: '#566157', strokeWidth: 2, strokeDasharray: '5 8' } }));

function App() {
  const sheet = useRef(null);
  const [ready, setReady] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  async function download() {
    setExporting(true);
    setError('');
    try {
      await document.fonts.ready;
      const url = await toPng(sheet.current, {
        pixelRatio: 2, backgroundColor: '#080a09', cacheBust: true,
        style: { margin: '0' },
      });
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'SDR-research-workflow.png';
      anchor.click();
    } catch {
      setError('The image could not be exported. Please try again.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <nav className="toolbar" aria-label="Diagram actions">
        <span>H2 / React Flow</span>
        <button disabled={!ready || exporting} onClick={download}>{exporting ? 'Preparing image…' : ready ? 'Download PNG' : 'Preparing diagram…'}</button>
      </nav>
      {error && <p className="export-error" role="alert">{error}</p>}
      <main className="sheet-wrap">
        <article className="sheet" ref={sheet} data-ready={ready} aria-label="H2 SDR research workflow">
          <header className="page-header">
            <div className="brand-bar"><img src="/h2-logo.svg" alt="H2" /><span>GTM SYSTEMS / HIRING SIGNALS</span></div>
            <p className="eyebrow"><span /> THE RESEARCH WORKFLOW</p>
            <h1>From hiring signal to SDR brief.</h1>
            <p className="intro">Find relevant hiring. Check the evidence. Give the rep a useful place to start.</p>
          </header>
          <section className="diagram-section" aria-label="Hiring data becomes an evidence-backed SDR brief">
            <div className="column-labels"><span>INPUTS</span><span>THE SYSTEM</span><span>FOR THE REP</span></div>
            <div className="flow">
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes}
                fitView fitViewOptions={{ padding: 0.01, maxZoom: 1 }}
                minZoom={1} maxZoom={1} nodesDraggable={false} nodesConnectable={false}
                elementsSelectable={false} panOnDrag={false} zoomOnScroll={false}
                zoomOnPinch={false} zoomOnDoubleClick={false} preventScrolling={false}
                onInit={() => setReady(true)} />
            </div>
          </section>
          <section className="proof" aria-labelledby="proof-title">
            <div className="proof-account"><span className="eyebrow">FROM THE LIVE TEST</span><h2 id="proof-title">The Perfume Shop</h2></div>
            <div className="proof-fact"><strong>Relevant hire</strong><span>Creative production<br />and quality checks</span></div>
            <div className="proof-fact"><strong>20 matching ads</strong><span>Active Meta records<br />in the sample</span></div>
            <div className="proof-fact"><strong>3 possible contacts</strong><span>Including a senior creative<br />and production manager</span></div>
          </section>
          <section className="daily" aria-label="Proposed daily automation">
            <span className="next-label">NEXT STEP / DAILY RUN</span>
            <p>Fresh briefs for your target accounts each morning.<br /><span>Scheduling and delivery are not enabled in this demo.</span></p>
          </section>
          <footer><span>Ad activity and current roles are provider-reported. Reps review before outreach.</span><span>h2.studio</span></footer>
        </article>
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
