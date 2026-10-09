const labels = {
  checking: "Connecting",
  connected: "Connected",
  unavailable: "API unavailable",
};


export function ApiStatus({ health }) {
  return (
    <div className={`connection connection--${health.state}`} role="status">
      <span className="connectionDot" aria-hidden="true" />
      {labels[health.state]}
    </div>
  );
}

