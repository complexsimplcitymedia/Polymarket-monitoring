/**
 * The device feed URL for the current origin. The noVNC page and its WebSocket go through
 * this site's own /vnc/ proxy (docker/nginx/default.conf), so the iframe uses the same scheme
 * as the dashboard: HTTPS/WSS on the public domain, plain HTTP/WS over the tailnet.
 */
export function getSecureVncUrl(): string {
    const { origin, protocol, port, hostname } = window.location
    const isHttps = protocol === 'https:'
    const url = new URL('/vnc/vnc.html', origin)
    url.searchParams.set('autoconnect', 'true')
    url.searchParams.set('show_dot', 'true')
    url.searchParams.set('encrypt', isHttps ? 'true' : 'false')
    url.searchParams.set('host', hostname)
    url.searchParams.set('port', port || (isHttps ? '443' : '80'))
    url.searchParams.set('path', 'vnc/websockify')
    return url.toString()
}
