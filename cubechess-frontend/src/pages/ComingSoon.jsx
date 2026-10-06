import Logo from '../components/Logo.jsx'

// Placeholder for the pages that are designed but not built yet
export default function ComingSoon({ title, children }) {
  return (
    <div className="page">
      <header className="bar">
        <Logo />
        <a className="bar-link" href="#/">
          Back to home
        </a>
      </header>
      <main className="soon">
        <h1>{title}</h1>
        <p>{children}</p>
        <a className="button button-primary button-large" href="#/setup">
          Play a game instead
        </a>
      </main>
    </div>
  )
}
