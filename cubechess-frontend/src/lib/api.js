// Thin wrapper over the Flask API. Vite proxies /api to the backend in development.

export async function api(path, body) {
  const options =
    body === undefined
      ? {}
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
  const response = await fetch('/api' + path, options)
  return response.json()
}

export const legalMovesOf = (coord) => api('/game/legal-moves?from=' + encodeURIComponent(JSON.stringify(coord)))
