import React, { useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, Handle, Position, MarkerType } from '@xyflow/react';
import { toPng } from 'html-to-image';
import '@xyflow/react/dist/style.css';
import './style.css';

const steps = [
  ['Find relevant hiring', 'Creative production, operations and measurement roles.'],
  ['Read what the role actually owns', 'Look for creative quality checks, standards and work across channels.'],
  ['Check Meta advertising', 'Match active ad records to the advertiser and company website.'],
  ['Find possible people to speak to', 'Rank relevant roles at the company and include profile links.'],
  ['Prepare the SDR brief', 'Why this account, evidence, possible contacts and a conversation starter.'],
];

function StepNode({ data }) {
  return (
    <div className={`step ${data.number === 5 ? 'step-final' : ''}`}>
      {data.number > 1 && <Handle type="target" position={Position.Top} />}
      <span className="step-number">{String(data.number).padStart(2, '0')}</span>
      <div className="step-copy">
        <h2>{data.title}</h2>
        <p>{data.description}</p>
      </div>
      {data.number < 5 && <Handle type="source" position={Position.Bottom} />}
    </div>
  );
}

const nodeTypes = { step: StepNode };
const nodes = steps.map(([title, description], index) => ({
  id: String(index + 1), type: 'step', position: { x: 0, y: index * 184 },
  data: { number: index + 1, title, description },
  ariaLabel: `Step ${index + 1}: ${title}. ${description}`,
}));
const edges = steps.slice(1).map((_, index) => ({
  id: `${index + 1}-${index + 2}`, source: String(index + 1), target: String(index + 2),
  type: 'straight', style: { stroke: '#8caaa3', strokeWidth: 2.5 },
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#8caaa3' },
}));

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
        pixelRatio: 2, backgroundColor: '#fbfcfa', cacheBust: true,
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
        <span>Built with React Flow</span>
        <button disabled={!ready || exporting} onClick={download}>
          {exporting ? 'Preparing image…' : ready ? 'Download PNG' : 'Preparing diagram…'}
        </button>
      </nav>
      {error && <p className="export-error" role="alert">{error}</p>}
      <main className="sheet-wrap">
        <article className="sheet" ref={sheet} data-ready={ready} aria-label="SDR research workflow">
          <header className="page-header">
            <p className="eyebrow">SDR RESEARCH WORKFLOW</p>
            <h1>From hiring signal<br />to SDR brief</h1>
            <p className="intro">A useful reason to speak to an account, with the research already done.</p>
          </header>

          <section className="flow" aria-label="Five steps in the tested workflow">
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes}
              fitView fitViewOptions={{ padding: 0.015, maxZoom: 1 }}
              minZoom={1} maxZoom={1} nodesDraggable={false}
              nodesConnectable={false} elementsSelectable={false}
              panOnDrag={false} zoomOnScroll={false} zoomOnPinch={false}
              zoomOnDoubleClick={false} preventScrolling={false}
              onInit={() => setReady(true)}
            />
          </section>

          <section className="proof" aria-labelledby="proof-title">
            <p className="eyebrow">FROM THE LIVE TEST</p>
            <h2 id="proof-title">The Perfume Shop</h2>
            <div className="proof-facts">
              <div><strong>Relevant hire</strong><span>Creative production<br />and quality checks</span></div>
              <div><strong>20 matching ads</strong><span>Active Meta records<br />in the sample</span></div>
              <div><strong>3 possible contacts</strong><span>Including a senior creative<br />and production manager</span></div>
            </div>
            <p className="evidence-note">Ad activity and current roles are provider-reported.</p>
          </section>

          <section className="daily" aria-labelledby="daily-title">
            <span className="next-label">NEXT STEP</span>
            <div>
              <h2 id="daily-title">A daily run for your target accounts</h2>
              <p>Fresh briefs waiting for the team each morning.</p>
              <p className="future-note">Scheduling and delivery are not enabled in this demo.</p>
            </div>
          </section>
          <footer>Research first. Reps review the evidence and choose the approach.</footer>
        </article>
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
