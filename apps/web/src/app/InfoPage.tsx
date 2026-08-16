import { Link } from "react-router-dom";

interface InfoPageProps {
  title: string;
  children: React.ReactNode;
}

export function InfoPage({ title, children }: InfoPageProps) {
  return (
    <main className="info-page">
      <span className="speaker-mark">THESOS</span>
      <h1>{title}</h1>
      <div>{children}</div>
      <Link to="/">Return to the Archives</Link>
    </main>
  );
}
