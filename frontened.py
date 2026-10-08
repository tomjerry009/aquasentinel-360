import { useEffect, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

export default function App() {
  const [data, setData] = useState(null);
  const [whatIf, setWhatIf] = useState(null);
  const [connection, setConnection] = useState("Connecting");

  useEffect(() => {
    let socket;
    let reconnectTimer;

    async function loadInitialState() {
      try {
        const response = await fetch(`${API}/api/state`);
        setData(await response.json());
      } catch {
        setConnection("Backend unavailable");
      }
    }

    function connectWebSocket() {
      socket = new WebSocket("ws://localhost:8000/ws");

      socket.onopen = () => setConnection("Live");
      socket.onmessage = (event) => {
        setData(JSON.parse(event.data));
      };
      socket.onclose = () => {
        setConnection("Reconnecting");
        reconnectTimer = setTimeout(connectWebSocket, 1500);
      };
      socket.onerror = () => socket.close();
    }

    loadInitialState();
    connectWebSocket();

    return () => {
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  async function post(path) {
    try {
      const response = await fetch(`${API}${path}`, { method: "POST" });
      setData(await response.json());
    } catch {
      alert("Could not connect to the backend.");
    }
  }

  async function loadWhatIf() {
    try {
      const response = await fetch(`${API}/api/what-if`);
      setWhatIf(await response.json());
    } catch {
      alert("Could not load the what-if estimate.");
    }
  }

  if (!data) {
    return <main className="page"><p>Connecting to AquaSentinel backend…</p></main>;
  }

  const incident = data.incident;

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">WATER NETWORK MAINTENANCE COPILOT</p>
          <h1>AquaSentinel <span>360</span></h1>
          <p className="subtitle">
            Detect → Verify → Explain → Localize → Prioritize → Predict → Act
          </p>
        </div>
        <div className={`connection ${connection === "Live" ? "live" : ""}`}>
          <span className="dot" /> {connection}
        </div>
      </header>

      <section className="actions">
        <button className="primary" onClick={() => post("/api/simulate/burst")}>
          Simulate Zone C3 Burst
        </button>
        <button className="secondary" onClick={() => post("/api/reset")}>
          Reset Demo
        </button>
        <span className="updated">
          Last update: {data.updated_at ? new Date(data.updated_at).toLocaleTimeString() : "—"}
        </span>
      </section>

      <section className="summary-grid">
        <article className="metric">
          <span>Network status</span>
          <strong className={incident ? "text-red" : "text-green"}>
            {incident ? "Incident detected" : "All zones healthy"}
          </strong>
        </article>
        <article className="metric">
          <span>Active incident</span>
          <strong>{incident ? incident.type : "None"}</strong>
        </article>
        <article className="metric">
          <span>Estimated water loss</span>
          <strong>{incident ? `${incident.estimated_loss_lph} L/hour` : "0 L/hour"}</strong>
        </article>
        <article className="metric">
          <span>Priority</span>
          <strong className={incident ? "text-red" : "text-green"}>
            {incident ? incident.priority : "—"}
          </strong>
        </article>
      </section>

      <div className="content-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Live network zones</h2>
              <p>Sensor readings compared with Digital Twin expectations</p>
            </div>
            <span className="live-label">LIVE TELEMETRY</span>
          </div>

          <div className="zone-grid">
            {data.zones.map((zone) => (
              <article
                className={`zone-card ${zone.status === "Incident" ? "zone-alert" : ""}`}
                key={zone.id}
              >
                <div className="zone-title">
                  <strong>Zone {zone.id}</strong>
                  <span className={zone.status === "Incident" ? "badge red" : "badge green"}>
                    {zone.status}
                  </span>
                </div>

                <div className="reading">
                  <span>Flow</span>
                  <strong>{zone.flow_lph.toLocaleString()} <small>L/h</small></strong>
                </div>
                <div className="reading">
                  <span>Expected flow</span>
                  <strong>{zone.expected_flow_lph.toLocaleString()} <small>L/h</small></strong>
                </div>
                <div className="reading">
                  <span>Pressure</span>
                  <strong>{zone.pressure_bar} <small>bar</small></strong>
                </div>

                <div className="twin-row">
                  Digital Twin mismatch
                  <strong>{zone.digital_twin_mismatch}</strong>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel incident-panel">
          <div className="panel-heading">
            <div>
              <h2>Incident decision support</h2>
              <p>Evidence, localization, and recommended response</p>
            </div>
          </div>

          {incident ? (
            <>
              <div className="incident-title">
                <div>
                  <span className="badge red">{incident.priority}</span>
                  <h3>{incident.type}</h3>
                </div>
                <strong className="confidence">{incident.confidence}%</strong>
              </div>

              <p className="location">
                Likely location: <strong>Zone {incident.zone} · {incident.asset}</strong>
              </p>

              <h4>Why this incident was raised</h4>
              <ul className="evidence">
                {incident.evidence.map((item) => <li key={item}>{item}</li>)}
              </ul>

              <div className="loss-callout">
                <strong>{incident.estimated_loss_lph} L/hour</strong>
                <span>Prototype water-loss estimate</span>
              </div>

              <p className="recommendation">{incident.recommendation}</p>

              <div className="button-row">
                <button
                  className="primary"
                  disabled={incident.acknowledged}
                  onClick={() => post("/api/incident/acknowledge")}
                >
                  {incident.acknowledged ? "Acknowledged" : "Acknowledge"}
                </button>
                <button
                  className="secondary"
                  disabled={incident.dispatched}
                  onClick={() => post("/api/incident/dispatch")}
                >
                  {incident.dispatched ? "Dispatch recorded" : "Dispatch technician"}
                </button>
              </div>

              <div className="whatif">
                <div className="whatif-heading">
                  <div>
                    <h4>What if the response is delayed?</h4>
                    <p>Additional prototype loss estimate</p>
                  </div>
                  <button className="small-button" onClick={loadWhatIf}>Calculate</button>
                </div>
                {whatIf && (
                  <div className="scenario-row">
                    {whatIf.scenarios.map((scenario) => (
                      <div className="scenario" key={scenario.hours}>
                        <span>Wait {scenario.hours}h</span>
                        <strong>{scenario.additional_loss_liters.toLocaleString()} L</strong>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <div className="healthy-icon">✓</div>
              <h3>No active incidents</h3>
              <p>All monitored zones are currently within the demo baseline.</p>
            </div>
          )}
        </section>
      </div>

      <section className="panel timeline-panel">
        <div className="panel-heading">
          <div>
            <h2>Incident timeline</h2>
            <p>Recent detection and operator events</p>
          </div>
        </div>
        {data.events.length ? (
          <div className="timeline">
            {data.events.slice(0, 8).map((event, index) => (
              <div className="timeline-item" key={`${event.timestamp}-${index}`}>
                <span className="timeline-dot" />
                <time>{new Date(event.timestamp).toLocaleTimeString()}</time>
                <span>{event.message}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No events yet. Start the burst simulation to see the workflow.</p>
        )}
      </section>

      <footer>
        Demo estimates only. Production use requires utility-specific sensor validation and calibration.
      </footer>
    </main>
  );
}
