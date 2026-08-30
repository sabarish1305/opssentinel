import { useState } from "react";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Gauge,
  LockKeyhole,
  RotateCcw,
  Server,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";

import "./App.css";

const evidence = [
  {
    icon: Server,
    title: "Service health inspected",
    detail: "checkout-api is reachable but degraded",
  },
  {
    icon: Gauge,
    title: "Latency measured",
    detail: "808.52 ms average response time",
  },
  {
    icon: FileText,
    title: "Runtime logs analyzed",
    detail: "800 ms degraded-mode delay detected",
  },
  {
    icon: Database,
    title: "Deployment correlated",
    detail: "v1.1.0 degraded · v1.0.0 known healthy",
  },
  {
    icon: TerminalSquare,
    title: "Sandbox diagnosis completed",
    detail: "TrueForge Daytona execution confirmed deployment regression",
  },
];

const licenseLevels = [
  { level: "L0", name: "Observe", status: "complete" },
  { level: "L1", name: "Diagnose", status: "complete" },
  { level: "L2", name: "Prepare", status: "active" },
  { level: "L3", name: "Act", status: "locked" },
];

function App() {
  const [phase, setPhase] = useState("investigating");

  const displayedLicenseLevels =
    phase === "approval"
      ? [
          { level: "L0", name: "Observe", status: "complete" },
          { level: "L1", name: "Diagnose", status: "complete" },
          { level: "L2", name: "Prepare", status: "complete" },
          {
            level: "L3",
            name: "Act",
            status: "locked",
            label: "Approval Required",
          },
        ]
      : phase === "recovered"
        ? [
            { level: "L0", name: "Observe", status: "complete" },
            { level: "L1", name: "Diagnose", status: "complete" },
            { level: "L2", name: "Prepare", status: "complete" },
            {
              level: "L3",
              name: "Act",
              status: "complete",
              label: "Completed",
            },
          ]
        : licenseLevels;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={22} />
          </div>

          <div>
            <p className="eyebrow">AUTONOMOUS INCIDENT RESPONSE</p>
            <h1>OpsSentinel</h1>
          </div>
        </div>

        <div className="agent-status">
          <span className="pulse-dot" />
          TRUEFORGE AGENT ONLINE
        </div>
      </header>

      <section className="incident-banner">
        <div>
          <div
            className={`incident-label ${
              phase === "recovered" ? "incident-label-success" : ""
            }`}
          >
            {phase === "recovered" ? (
              <CheckCircle2 size={17} />
            ) : (
              <AlertTriangle size={17} />
            )}

            {phase === "recovered" ? "RECOVERY VERIFIED" : "ACTIVE INCIDENT"}
          </div>

          <h2>
            {phase === "recovered"
              ? "Checkout API restored"
              : "Checkout API performance degradation"}
          </h2>

          <p>
            {phase === "recovered"
              ? "Post-recovery verification confirms the service is healthy and operating on the known-good release."
              : "Correlated evidence indicates the latest deployment introduced severe response latency."}
          </p>
        </div>

        <div className="incident-meta">
          <div>
            <span>SEVERITY</span>
            <strong>{phase === "recovered" ? "RESOLVED" : "SEV-2"}</strong>
          </div>

          <div>
            <span>STATUS</span>
            <strong>
              {phase === "recovered" ? "HEALTHY" : "INVESTIGATING"}
            </strong>
          </div>

          <div>
            <span>INCIDENT</span>
            <strong>INC-0042</strong>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <article className="metric-card">
          <div className="metric-icon">
            <Activity size={20} />
          </div>

          <div>
            <span>Service health</span>
            <strong
              className={
                phase === "recovered" ? "success-text" : "danger-text"
              }
            >
              {phase === "recovered" ? "HEALTHY" : "DEGRADED"}
            </strong>
          </div>
        </article>

        <article className="metric-card">
          <div className="metric-icon">
            <Server size={20} />
          </div>

          <div>
            <span>Current version</span>
            <strong>{phase === "recovered" ? "1.0.0" : "1.1.0"}</strong>
          </div>
        </article>

        <article className="metric-card">
          <div className="metric-icon">
            <Gauge size={20} />
          </div>

          <div>
            <span>Checkout latency</span>
            <strong
              className={
                phase === "recovered" ? "success-text" : "danger-text"
              }
            >
              {phase === "recovered" ? "87.61 ms" : "808.52 ms"}
            </strong>
          </div>
        </article>

        <article className="metric-card">
          <div className="metric-icon">
            <Clock3 size={20} />
          </div>

          <div>
            <span>Known healthy</span>
            <strong>1.0.0</strong>
          </div>
        </article>
      </section>

      <section className="content-grid">
        <article className="panel evidence-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">EVIDENCE PIPELINE</p>
              <h3>Investigation timeline</h3>
            </div>

            <span className="read-only-badge">
              <LockKeyhole size={14} />
              READ ONLY
            </span>
          </div>

          <div className="evidence-list">
            {evidence.map((item, index) => {
              const Icon = item.icon;

              return (
                <div className="evidence-item" key={item.title}>
                  <div className="timeline-column">
                    <div className="evidence-check">
                      <CheckCircle2 size={17} />
                    </div>

                    {index !== evidence.length - 1 && (
                      <div className="timeline-line" />
                    )}
                  </div>

                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                  </div>

                  <Icon className="evidence-icon" size={18} />
                </div>
              );
            })}
          </div>
        </article>

        <article className="panel diagnosis-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">SANDBOX DIAGNOSIS</p>
              <h3>Root cause</h3>
            </div>

            <div className="sandbox-badge">
              <TerminalSquare size={14} />
              DAYTONA
            </div>
          </div>

          <div className="diagnosis-box">
            <p className="diagnosis-kicker">DEPLOYMENT RELATED</p>

            <h4>Version 1.1.0 introduced an 800 ms response delay.</h4>

            <p>
              Health degradation, runtime warnings, latency measurements and
              deployment history independently converge on the latest release.
            </p>
          </div>

          <div className="diagnosis-stats">
            <div>
              <span>Observed</span>
              <strong>808.52 ms</strong>
            </div>

            <div>
              <span>Injected delay</span>
              <strong>800 ms</strong>
            </div>

            <div>
              <span>Confidence</span>
              <strong>HIGH</strong>
            </div>
          </div>
        </article>
      </section>

      <section className="panel license-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">PROGRESSIVE CONTROL</p>
            <h3>License to Act</h3>
          </div>

          <span className="control-badge">
            <ShieldCheck size={14} />
            HUMAN CONTROLLED
          </span>
        </div>

        <div className="license-track">
          {displayedLicenseLevels.map((item) => (
            <div
              className={`license-level ${item.status}`}
              key={item.level}
            >
              <div className="license-number">{item.level}</div>

              <div>
                <strong>{item.name}</strong>

                <span>
                  {item.label ??
                    (item.status === "complete"
                      ? "Completed"
                      : item.status === "active"
                        ? "Ready"
                        : "Locked")}
                </span>
              </div>
            </div>
          ))}
        </div>

        {phase === "investigating" ? (
          <div className="recovery-action">
            <div>
              <p className="eyebrow">RECOMMENDED NEXT ACTION</p>
              <h3>Prepare rollback to known-healthy version 1.0.0</h3>

              <p>
                Preparation is read-only. Execution remains locked until
                explicit human approval is granted.
              </p>
            </div>

            <button onClick={() => setPhase("approval")}>
              <RotateCcw size={18} />
              Prepare Recovery
            </button>
          </div>
        ) : phase === "approval" ? (
          <div className="recovery-action approval-required">
            <div>
              <p className="eyebrow">HUMAN APPROVAL REQUIRED</p>
              <h3>Rollback plan prepared: 1.1.0 → 1.0.0</h3>

              <p>
                L3 remains locked until TrueForge receives explicit human
                approval and OpsSentinel validates the signed approval token.
              </p>
            </div>

            <button onClick={() => setPhase("recovered")}>
              <ShieldCheck size={18} />
              Show Verified Recovery
            </button>
          </div>
        ) : (
          <div className="recovery-action recovered-action">
            <div>
              <p className="eyebrow">RECOVERY VERIFIED</p>
              <h3>Checkout API restored to known-healthy version 1.0.0</h3>

              <p>
                Post-recovery verification confirms healthy service status and
                checkout latency reduced from 808.52 ms to 87.61 ms.
              </p>
            </div>

            <button onClick={() => setPhase("investigating")}>
              <RotateCcw size={18} />
              Reset Demo Scenario
            </button>
          </div>
        )}
      </section>

      <footer>
        <span>OpsSentinel · Evidence-first incident response</span>
        <span>Investigate automatically. Act only with a license.</span>
      </footer>
    </main>
  );
}

export default App;