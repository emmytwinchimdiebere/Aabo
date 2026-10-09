export function AppHeader({ status }) {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Emergency operations</p>
        <h1>Aabo 112</h1>
      </div>
      {status}
    </header>
  );
}

