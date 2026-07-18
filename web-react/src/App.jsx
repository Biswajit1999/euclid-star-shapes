import { Component, lazy, Suspense, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowDownToLine,
  Beaker,
  BookOpen,
  CheckCircle2,
  CircleDot,
  Database,
  ExternalLink,
  FileText,
  GitCommit,
  Orbit,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

const TelescopeHero = lazy(() => import('./TelescopeHero.jsx'));

const warningRules = [
  {
    key: 'sample-size',
    label: 'Underpowered magnitude bins',
    description: 'Bins below the declared minimum sample size remain visible but are not treated as well-powered estimates.',
    pattern: /below minimum(?:_sample_size| sample size)|too few|underpowered|n\s*[<≤]\s*\d+/i,
    tone: 'caveat',
  },
  {
    key: 'gaia-coverage',
    label: 'Gaia cross-match coverage',
    description: 'The selected field did not supply enough matches for the registered astrometric comparison.',
    pattern: /gaia|affine alignment|match radius/i,
    tone: 'caveat',
  },
  {
    key: 'covariance',
    label: 'Ill-conditioned fit covariance',
    description: 'Fit covariance exceeded the numerical conditioning gate.',
    pattern: /covariance|condition number|ill[- ]conditioned/i,
    tone: 'caveat',
  },
  {
    key: 'convergence',
    label: 'Non-convergent fits',
    description: 'Candidate fits that did not converge were retained in the audit trail.',
    pattern: /did not converge|non[- ]convergent|convergence/i,
    tone: 'caveat',
  },
  {
    key: 'physical-range',
    label: 'Physical-range rejections',
    description: 'Values outside the declared physical gate were rejected from inference.',
    pattern: /physically implausible|physical range|outside.*range|rejected/i,
    tone: 'caveat',
  },
  {
    key: 'failure',
    label: 'Validation failures',
    description: 'These entries indicate a failed validation condition and require direct attention.',
    pattern: /fatal|zero[- ]tolerance|validation fail|\berror\b/i,
    tone: 'failure',
  },
];

function parseResultJson(text) {
  // Python emits NaN for an unavailable metric. Preserve the source file while
  // presenting that value as unavailable in standards-compliant browser data.
  return JSON.parse(text.replace(/:\s*NaN(?=\s*[,}])/g, ': null'));
}

function useJson(path) {
  const [state, setState] = useState({ data: null, error: null, loading: true });

  useEffect(() => {
    const controller = new AbortController();
    fetch(path, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
        return response.text();
      })
      .then((text) => setState({ data: parseResultJson(text), error: null, loading: false }))
      .catch((error) => {
        if (error.name !== 'AbortError') setState({ data: null, error, loading: false });
      });
    return () => controller.abort();
  }, [path]);

  return state;
}

function formatValue(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not available';
  return value.toPrecision(4);
}

function SectionHeading({ eyebrow, title, copy }) {
  return (
    <div className="section-heading">
      <p>{eyebrow}</p>
      <h2>{title}</h2>
      {copy && <span>{copy}</span>}
    </div>
  );
}

function MetricCard({ metric, index }) {
  const hasUncertainty = metric.uncertainty_low != null && metric.uncertainty_high != null;
  const unavailable = typeof metric.estimate !== 'number' || !Number.isFinite(metric.estimate);

  return (
    <article className="metric-card">
      <div className="metric-index">{String(index + 1).padStart(2, '0')}</div>
      <p className="metric-name">{metric.name.replace(/_/g, ' ')}</p>
      <p className={`metric-value ${unavailable ? 'metric-unavailable' : ''}`}>
        {formatValue(metric.estimate)}
        {!unavailable && <span>{metric.units}</span>}
      </p>
      {hasUncertainty && (
        <p className="metric-note">
          95% CI [{metric.uncertainty_low.toPrecision(3)}, {metric.uncertainty_high.toPrecision(3)}]
        </p>
      )}
      <p className="metric-sample">sample size · {metric.sample_size}</p>
    </article>
  );
}

function DataPanel({ icon: Icon, title, children, className = '' }) {
  return (
    <article className={`data-panel ${className}`}>
      <div className="data-panel-title">
        <Icon size={17} aria-hidden="true" />
        <h3>{title}</h3>
      </div>
      {children}
    </article>
  );
}

function groupWarnings(entries) {
  const groups = new Map();
  entries.forEach((entry, index) => {
    const text = String(entry);
    const rule = warningRules.find(({ pattern }) => pattern.test(text)) ?? {
      key: 'other',
      label: 'Other documented caveats',
      description: 'Additional pipeline context retained for reproducibility.',
      tone: 'caveat',
    };
    const current = groups.get(rule.key) ?? { ...rule, entries: [] };
    current.entries.push({ text, index });
    groups.set(rule.key, current);
  });
  return [...groups.values()];
}

function WarningsPanel({ warnings }) {
  const entries = useMemo(() => (Array.isArray(warnings.data) ? warnings.data : []), [warnings.data]);
  const groups = useMemo(() => groupWarnings(entries), [entries]);

  if (warnings.loading) return <p className="muted-copy">Loading the warning audit trail…</p>;
  if (warnings.error) {
    return <p className="warning-load-error">Could not load results/warnings.json: {String(warnings.error)}</p>;
  }
  if (entries.length === 0) {
    return (
      <div className="warning-empty">
        <CheckCircle2 size={19} aria-hidden="true" />
        No warnings recorded in results/warnings.json.
      </div>
    );
  }

  return (
    <div>
      <div className="warning-summary">
        <div>
          <strong>{entries.length}</strong>
          <span>documented entries</span>
        </div>
        <p>
          These are transparent caveats and coverage limits, not a crash log. Counts are grouped for
          scanning; every source entry remains available below.
        </p>
      </div>
      <div className="warning-groups">
        {groups.map((group) => (
          <div className={`warning-group warning-${group.tone}`} key={group.key}>
            <div className="warning-count">{group.entries.length}</div>
            <div>
              <h3>{group.label}</h3>
              <p>{group.description}</p>
            </div>
          </div>
        ))}
      </div>
      <details className="raw-warning-details">
        <summary>Show all {entries.length} raw entries</summary>
        <ol>
          {entries.map((entry, index) => <li key={`${index}-${String(entry)}`}>{String(entry)}</li>)}
        </ol>
      </details>
    </div>
  );
}

function inverseNormalCDF(p) {
  if (p <= 0 || p >= 1) return Number.NaN;
  const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
  const b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
  const c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
  const d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
  const pLow = 0.02425;
  const pHigh = 1 - pLow;
  let q;
  let r;
  if (p < pLow) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p <= pHigh) {
    q = p - 0.5;
    r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  q = Math.sqrt(-2 * Math.log(1 - p));
  return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
}

function ConfidenceExplorer({ metrics }) {
  const withIntervals = (metrics ?? []).filter((metric) => metric.uncertainty_low != null && metric.uncertainty_high != null);
  const [selected, setSelected] = useState(withIntervals[0]?.name ?? '');
  const [confidence, setConfidence] = useState(95);
  if (withIntervals.length === 0) return null;

  const metric = withIntervals.find((item) => item.name === selected) ?? withIntervals[0];
  const sigma = ((metric.uncertainty_high - metric.uncertainty_low) / 2) / 1.959963984540054;
  const zLevel = inverseNormalCDF(0.5 + confidence / 200);
  const low = metric.estimate - zLevel * sigma;
  const high = metric.estimate + zLevel * sigma;

  return (
    <DataPanel icon={Beaker} title="Confidence-level explorer" className="confidence-panel">
      <p className="muted-copy">
        Approximate client-side sensitivity view derived from the reported 95% bootstrap interval.
        It does not re-run the bootstrap.
      </p>
      {withIntervals.length > 1 && (
        <select value={metric.name} onChange={(event) => setSelected(event.target.value)}>
          {withIntervals.map((item) => <option key={item.name} value={item.name}>{item.name.replace(/_/g, ' ')}</option>)}
        </select>
      )}
      <label className="range-label">
        <span>Confidence level</span>
        <strong>{confidence.toFixed(1)}%</strong>
      </label>
      <input type="range" min="50" max="99.9" step="0.1" value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} />
      <p className="interval-readout">[{low.toPrecision(4)}, {high.toPrecision(4)}] <span>{metric.units}</span></p>
    </DataPanel>
  );
}

class HeroBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return <div className="hero-visual-fallback">Interactive optics view unavailable.</div>;
    return this.props.children;
  }
}

export default function App() {
  const project = useJson('./project.json');
  const summary = useJson('./results/summary.json');
  const warnings = useJson('./results/warnings.json');
  const benchmarks = useJson('./results/benchmarks.json');

  if (project.loading) return <main className="loading-screen">Loading project metadata…</main>;
  if (project.error || !project.data) {
    return <main className="loading-screen loading-error">Could not load project.json: {String(project.error)}</main>;
  }

  const p = project.data;
  const isDemo = summary.data?.data_kind === 'synthetic_smoke_test' || summary.data?.data_kind === 'synthetic_demo';

  return (
    <main className="euclid-shell">
      <div className="aurora aurora-one" aria-hidden="true" />
      <div className="aurora aurora-two" aria-hidden="true" />
      <div className="page-frame">
        <nav className="top-nav" aria-label="Page sections">
          <a className="brand-mark" href="#top" aria-label="Euclid star-shapes audit home">
            <Orbit size={20} aria-hidden="true" />
            <span>VIS / shape audit</span>
          </a>
          <div>
            <a href="#findings">Findings</a>
            <a href="#evidence">Evidence</a>
            <a href="#method">Method</a>
            <a href="#reproduce">Reproduce</a>
          </div>
        </nav>

        <header className="hero" id="top">
          <div className="hero-copy">
            <p className="hero-kicker"><Sparkles size={14} aria-hidden="true" /> {p.category}</p>
            <h1>{p.title}</h1>
            <p className="hero-question">{p.question}</p>
            <div className="hero-tags">
              <span className="tag tag-primary">{p.status}</span>
              <span className="tag">Priority {p.priority}/10</span>
              <span className="tag">{p.dataMode}</span>
            </div>
            {summary.data && (
              <div className={`result-ribbon ${isDemo ? 'result-demo' : 'result-real'}`}>
                <CircleDot size={15} aria-hidden="true" />
                {isDemo ? 'Synthetic demo results' : 'Real public-data results'}
              </div>
            )}
          </div>
          <figure className="hero-figure">
            <HeroBoundary>
              <Suspense fallback={<div className="hero-visual-fallback">Loading optics illustration…</div>}>
                <TelescopeHero />
              </Suspense>
            </HeroBoundary>
            <figcaption>Stylized illustration, not flight data</figcaption>
          </figure>
        </header>

        {isDemo && (
          <div className="demo-banner">
            <AlertTriangle size={19} aria-hidden="true" />
            <p>
              Metrics and figures were generated from clearly labelled synthetic demo data, not Euclid VIS observations.
              Real-data output replaces these assets after the archive workflow is run.
            </p>
          </div>
        )}

        <section className="findings-section" id="findings">
          <SectionHeading eyebrow="01 / instrument readout" title="Measured shape diagnostics" copy="The first six published metrics, read directly from results/summary.json." />
          {summary.error && <p className="warning-load-error">Could not load results/summary.json: {String(summary.error)}</p>}
          <div className="metric-grid">
            {summary.data?.metrics?.slice(0, 6).map((metric, index) => <MetricCard key={metric.name} metric={metric} index={index} />)}
            {!summary.loading && !summary.data && !summary.error && (
              <article className="metric-card metric-empty"><p>No results yet. Run scripts/run_analysis.py first.</p></article>
            )}
          </div>
          <ConfidenceExplorer metrics={summary.data?.metrics} />
        </section>

        <section className="evidence-section" id="evidence">
          <SectionHeading eyebrow="02 / optical evidence" title="Six views of point-source behaviour" copy="Publication figures remain white-field assets for legibility against the indigo interface." />
          <div className="evidence-layout">
            <div className="figure-gallery">
              {p.figures.map((figure, index) => (
                <figure className={`figure-card ${index === 0 ? 'figure-feature' : ''}`} key={figure.id}>
                  <div className="figure-number">F{String(index + 1).padStart(2, '0')}</div>
                  <img src={`./figures/${figure.id}.svg`} alt={figure.label} loading="lazy" />
                  <figcaption>{figure.label}</figcaption>
                </figure>
              ))}
            </div>

            <aside className="evidence-spine">
              <DataPanel icon={ShieldCheck} title="Provenance boundary">
                <p className="panel-copy">{p.novelty}</p>
                <div className="provenance-gate">
                  <AlertTriangle size={17} aria-hidden="true" />
                  No result is public-ready until validation and provenance checks pass.
                </div>
                {summary.data?.provenance && (
                  <dl className="provenance-list">
                    <div><dt><GitCommit size={14} /> Git commit</dt><dd>{summary.data.provenance.git_commit}</dd></div>
                    <div><dt><FileText size={14} /> Config SHA-256</dt><dd title={summary.data.provenance.config_sha256}>{summary.data.provenance.config_sha256 ?? 'n/a'}</dd></div>
                    <div><dt><Beaker size={14} /> Package</dt><dd>{summary.data.provenance.package_version}</dd></div>
                  </dl>
                )}
              </DataPanel>

              <DataPanel icon={ShieldCheck} title="Validation contract">
                <ul className="contract-list">
                  {p.validationContract.map((item) => <li key={item}><CheckCircle2 size={15} aria-hidden="true" />{item}</li>)}
                </ul>
              </DataPanel>
            </aside>
          </div>
        </section>

        <section className="warnings-section">
          <SectionHeading eyebrow="03 / transparent audit trail" title="Warnings, grouped by scientific meaning" copy="Live categories and raw entries are sourced from results/warnings.json." />
          <WarningsPanel warnings={warnings} />
        </section>

        <section className="method-section" id="method">
          <SectionHeading eyebrow="04 / analysis boundary" title="Method, assumptions and limits" />
          <div className="method-grid">
            <DataPanel icon={Beaker} title="Methodology" className="methodology-panel">
              <p className="panel-copy panel-copy-large">{p.methodology}</p>
            </DataPanel>
            <DataPanel icon={BookOpen} title="Assumptions">
              <ol className="numbered-list">
                {p.assumptions.map((item, index) => <li key={item}><span>{String(index + 1).padStart(2, '0')}</span>{item}</li>)}
              </ol>
            </DataPanel>
            <DataPanel icon={AlertTriangle} title="Limitations" className="limitations-panel">
              <ol className="numbered-list">
                {p.limitations.map((item, index) => <li key={item}><span>{String(index + 1).padStart(2, '0')}</span>{item}</li>)}
              </ol>
            </DataPanel>
          </div>
        </section>

        <section className="reproduce-section" id="reproduce">
          <div>
            <SectionHeading eyebrow="05 / reproducibility" title="Take the evidence with you" copy="Machine-readable results, provenance tables and benchmark output." />
            <div className="download-grid">
              <a href="./manifest.csv" download><ArrowDownToLine size={17} />data/manifest.csv</a>
              <a href="./source_catalog.csv" download><ArrowDownToLine size={17} />data/source_catalog.csv</a>
              <a href="./results/summary.json" download><ArrowDownToLine size={17} />results/summary.json</a>
              {benchmarks.data && <a href="./results/benchmarks.json" download><ArrowDownToLine size={17} />results/benchmarks.json</a>}
            </div>
            <p className="manifest-note">
              The manifest records product identity, source URL, retrieval time, SHA-256, file size,
              selection reason and archive terms for each public product used.
            </p>
          </div>
          <DataPanel icon={Database} title="Citation and licence" className="citation-panel">
            <p>Author <strong>{p.citation.author}</strong></p>
            <p>Licence <strong>{p.citation.license}</strong></p>
            <a href={p.citation.repository}>Open repository <ExternalLink size={14} /></a>
          </DataPanel>
        </section>

        <footer>
          <span>Euclid Q1 VIS · external reproducibility audit</span>
          <span>Biswajit Jana</span>
        </footer>
      </div>
    </main>
  );
}
