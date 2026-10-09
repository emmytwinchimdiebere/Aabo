export function IncidentList({ incidents }) {
  return (
    <aside className="incidentPanel">
      <div className="sectionHeading">
        <h2>Incidents</h2>
        <span>{incidents.length} active</span>
      </div>

      {incidents.length === 0 ? (
        <div className="emptyState">
          <span className="emptyIcon" aria-hidden="true">A</span>
          <h3>No active incidents</h3>
          <p>Incoming reports will appear here for dispatcher review.</p>
        </div>
      ) : (
        <ol className="incidentList">
          {incidents.map((incident) => (
            <li key={incident.incident_id}>{incident.emergency.type}</li>
          ))}
        </ol>
      )}
    </aside>
  );
}
