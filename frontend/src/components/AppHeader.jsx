export function AppHeader({ status }) {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Emergency operations</p>
        <h1>Aabo</h1>
        <p>Call +234 201 350 2017</p>
      </div>
      {status}
    </header>
  );
}
