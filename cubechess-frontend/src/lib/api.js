// Thin wrapper over the Flask API. Vite proxies /api to the backend in development.
// The server keeps two games: "main" (the one being played) and "practice" (lessons).

function url(path, game) {
  if (!game || game === 'main') return '/api' + path
  return '/api' + path + (path.includes('?') ? '&' : '?') + 'game=' + game
}

export async function api(path, body, game) {
  const options =
    body === undefined
      ? {}
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
  const response = await fetch(url(path, game), options)
  return response.json()
}

export const legalMovesOf = (coord, game) =>
  api('/game/legal-moves?from=' + encodeURIComponent(JSON.stringify(coord)), undefined, game)
