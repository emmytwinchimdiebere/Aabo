import { useEffect, useMemo, useState } from "react";

import { getIncidents, getRecordingUrl } from "../../api/client";
import { ApiStatus } from "../../components/ApiStatus";
import { useApiHealth } from "../../hooks/useApiHealth";

const LANGUAGE_NAMES = { en: "Nigerian English", ig: "Igbo", ha: "Hausa", yo: "Yorùbá" };

function displayTime(value) {
  return new Intl.DateTimeFormat("en-NG", { dateStyle: "medium", timeStyle: "short" }).format(new Date(`${value}Z`));
}

export function DispatcherConsole() {
  const health = useApiHealth();
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const records = await getIncidents();
        if (cancelled) return;
        setIncidents(records);
        setSelectedId((current) => current || records[0]?.incident_id || "");
        setError("");
      } catch (requestError) {
        if (!cancelled) setError(requestError.message);
      }
    }
    refresh();
    const timer = window.setInterval(refresh, 5_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  const selected = useMemo(
    () => incidents.find((incident) => incident.incident_id === selectedId) ?? incidents[0],
    [incidents, selectedId],
  );

  return (
    <main className="dispatchShell">
      <header className="dispatchHeader">
        <a className="brandMark brandMark--dark" href="/dispatch"><span aria-hidden="true">A</span><div><strong>Aabo</strong><small>+234 201 350 2017</small></div></a>
        <div className="dispatchHeaderActions"><ApiStatus health={health} /><a href="/">Caller view ↗</a></div>
      </header>

      <section className="dispatchLayout">
        <aside className="incidentRail">
          <div className="railHeading"><div><p className="callerEyebrow">Live queue</p><h1>Incidents</h1></div><span>{incidents.length} total</span></div>
          {error && <div className="consoleError">{error}</div>}
          {!error && incidents.length === 0 && <div className="consoleEmpty"><span>A</span><h2>No reports yet</h2><p>Reports from +234 201 350 2017 and the web will appear here.</p></div>}
          <ol className="incidentCards">
            {incidents.map((incident) => (
              <li key={incident.incident_id}>
                <button className={incident.incident_id === selected?.incident_id ? "incidentCard incidentCard--active" : "incidentCard"} onClick={() => setSelectedId(incident.incident_id)} type="button">
                  <span className={`incidentType incidentType--${incident.emergency_type.toLowerCase()}`}>{incident.emergency_type}</span>
                  <strong>{incident.confirmed_address}</strong>
                  <small>{LANGUAGE_NAMES[incident.language]} · {displayTime(incident.created_at)}</small>
                </button>
              </li>
            ))}
          </ol>
        </aside>

        <section className="incidentDetail">
          {!selected ? <div className="detailEmpty"><p>Select an incident to review its details.</p></div> : (
            <>
              <header className="detailHeader">
                <div><p className="callerEyebrow">Incoming web report</p><h2>{selected.emergency_type} emergency</h2><p>{selected.incident_id} · {displayTime(selected.created_at)}</p></div>
                <span className="pendingBadge"><i /> Awaiting review</span>
              </header>

              <div className="detailGrid">
                <article className="detailCard recordingCard">
                  <div className="cardTitle"><div><span className="cardIcon" aria-hidden="true">♪</span><div><p>Original recording</p><small>{LANGUAGE_NAMES[selected.language]} · {selected.duration_seconds}s</small></div></div><span className="sourceBadge">Caller audio</span></div>
                  {selected.has_recording ? <audio controls preload="metadata" src={getRecordingUrl(selected.incident_id)}>Your browser cannot play this recording.</audio> : <p className="mutedText">No recording is available.</p>}
                  <p className="recordingHelp">Use the recording to verify names, landmarks, and addresses before dispatch.</p>
                </article>

                <article className="detailCard locationCard">
                  <div className="cardTitle"><div><span className="cardIcon" aria-hidden="true">⌖</span><div><p>Confirmed location</p><small>Caller reviewed</small></div></div><span className="verifiedBadge">✓ Confirmed</span></div>
                  <h3>{selected.confirmed_address}</h3>
                  {selected.latitude != null ? <p className="coordinates">{selected.latitude.toFixed(6)}, {selected.longitude.toFixed(6)}</p> : <p className="mutedText">No device coordinates attached</p>}
                  <div className="miniMap"><span className="mapPin">●</span><span className="mapRoad mapRoad--one" /><span className="mapRoad mapRoad--two" /></div>
                </article>

                <article className="detailCard transcriptCard">
                  <div className="cardTitle"><div><span className="cardIcon" aria-hidden="true">Aa</span><div><p>Speech transcript</p><small>N-ATLaS · {LANGUAGE_NAMES[selected.language]}</small></div></div></div>
                  <div className="transcriptCompare">
                    <div><span>Original ASR output</span><blockquote>{selected.raw_transcript}</blockquote></div>
                    <div className="confirmedCopy"><span>Caller-confirmed report</span><blockquote>{selected.confirmed_transcript}</blockquote></div>
                  </div>
                </article>

                <aside className="detailCard dispatchSummary">
                  <p className="summaryLabel">Dispatch summary</p>
                  <dl><div><dt>Type</dt><dd>{selected.emergency_type}</dd></div><div><dt>Language</dt><dd>{LANGUAGE_NAMES[selected.language]}</dd></div><div><dt>Source</dt><dd>Web voice</dd></div><div><dt>Status</dt><dd>{selected.dispatcher_status}</dd></div></dl>
                  <button type="button">Acknowledge incident</button>
                  <p>Verify the recording and location before dispatching a response unit.</p>
                </aside>
              </div>
            </>
          )}
        </section>
      </section>
    </main>
  );
}
