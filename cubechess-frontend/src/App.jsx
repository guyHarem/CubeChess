import { lazy, Suspense } from 'react'
import { useRoute } from './lib/router.js'
import ComingSoon from './pages/ComingSoon.jsx'
import Game from './pages/Game.jsx'
import Home from './pages/Home.jsx'
import Learn from './pages/Learn.jsx'
import Setup from './pages/Setup.jsx'
import './app.css'

// Developer tool for poking at backend behaviour, kept out of the main bundle
const TestBench = lazy(() => import('./bench/TestBench.jsx'))

export default function App() {
  const route = useRoute()

  if (route === '/setup') return <Setup />
  if (route === '/game') return <Game />
  if (route === '/learn') return <Learn />
  if (route === '/scenarios') {
    return <ComingSoon title="Scenarios are on the way">The scenario player is designed but not built yet. It is next.</ComingSoon>
  }
  if (route === '/bench') {
    return (
      <Suspense fallback={null}>
        <TestBench />
      </Suspense>
    )
  }
  return <Home />
}
