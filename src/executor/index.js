import Fastify from 'fastify'
import axios from 'axios'
import { SocksProxyAgent } from 'socks-proxy-agent'
import nacl from 'tweetnacl'
import fs from 'fs'

const fastify = Fastify({ logger: true })

const API_BASE_URL = process.env.POLYMARKET_US_API_URL || 'https://api.polymarket.us'
const KEY_ID = process.env.POLYMARKET_KEY_ID || process.env.POLYMARKET_API_KEY || ''
const SECRET = process.env.POLYMARKET_SECRET_KEY || process.env.POLYMARKET_SECRET || ''
const SOCKS_PROXY = process.env.TRADE_SOCKS_PROXY || ''

function readSecretFile() {
    const path = process.env.SECRET_KEY_FILE || '/run/secrets/polymarket_secret_key'
    try {
        return fs.readFileSync(path, 'utf8').trim()
    } catch {
        return ''
    }
}

const secretKey = SECRET || readSecretFile()

let proxyAgent = null
if (SOCKS_PROXY) {
    proxyAgent = new SocksProxyAgent(SOCKS_PROXY)
    fastify.log.info(`Order traffic routed through SOCKS proxy: ${SOCKS_PROXY}`)
}

function createAuthHeaders(method, path) {
    if (!KEY_ID || !secretKey) {
        throw new Error('Polymarket US API credentials not configured')
    }
    const timestamp = String(Date.now())
    const message = `${timestamp}${method}${path}`
    const secretBytes = Buffer.from(secretKey, 'base64')
    const seed = secretBytes.length === 64 ? secretBytes.slice(0, 32) : secretBytes
    const keyPair = nacl.sign.keyPair.fromSeed(seed)
    const signature = nacl.sign.detached(Buffer.from(message), keyPair.secretKey)
    return {
        'X-PM-Access-Key': KEY_ID,
        'X-PM-Timestamp': timestamp,
        'X-PM-Signature': Buffer.from(signature).toString('base64'),
    }
}

async function pmusRequest(method, path, body = null, query = null) {
    const url = `${API_BASE_URL}${path}`
    const headers = createAuthHeaders(method, path)
    const start = performance.now()
    const response = await axios({
        method,
        url,
        data: body,
        params: query,
        headers,
        timeout: 20000,
        httpsAgent: proxyAgent || undefined,
        proxy: false,
    })
    return { data: response.data, latencyMs: Math.round(performance.now() - start) }
}

function toOrderRequest(body) {
    if (body?.request) return body
    const {
        marketSlug,
        market_slug,
        intent,
        side,
        price,
        quantity,
        size,
        type,
        tif,
        tifValue,
        tif_label,
    } = body || {}

    const slug = marketSlug || market_slug
    if (!slug) {
        throw new Error('marketSlug is required')
    }

    const orderIntent = intent || (side === 'SELL' ? 'SELL' : 'BUY')
    const orderPrice = price ?? 0.5
    const orderQuantity = quantity ?? size ?? 1
    const orderType = type || 'LIMIT'
    const timeInForce = tif || tifValue || tif_label || 'GTC'

    return {
        request: {
            marketSlug: slug,
            intent: orderIntent,
            price: String(orderPrice),
            quantity: Number(orderQuantity),
            type: orderType,
            tif: timeInForce,
        },
    }
}

fastify.get('/health', async () => ({
    status: 'ok',
    proxy: SOCKS_PROXY || 'none',
    api_base: API_BASE_URL,
    key_id_prefix: KEY_ID ? `${KEY_ID.slice(0, 8)}...` : 'missing',
}))

fastify.get('/status', async () => ({
    status: 'READY',
    mode: 'polymarket-us',
    api_base: API_BASE_URL,
    proxy: SOCKS_PROXY || 'none',
    key_id_prefix: KEY_ID ? `${KEY_ID.slice(0, 8)}...` : 'missing',
}))

fastify.post('/order', async (request, reply) => {
    const dryRun = request.body?.dry_run ?? false
    const orderReq = toOrderRequest(request.body)
    try {
        const preview = await pmusRequest('POST', '/v1/order/preview', orderReq)
        if (dryRun) {
            return {
                success: true,
                dry_run: true,
                latency_ms: preview.latencyMs,
                preview: preview.data,
            }
        }
        const order = await pmusRequest('POST', '/v1/orders', orderReq)
        return {
            success: true,
            latency_ms: order.latencyMs,
            preview_latency_ms: preview.latencyMs,
            response: order.data,
        }
    } catch (err) {
        reply.status(err.response?.status || 400)
        return {
            success: false,
            latency_ms: err.latencyMs || null,
            error: err.response?.data || err.message,
        }
    }
})

fastify.post('/parlay', async (request, reply) => {
    const { legs, total_budget, dry_run = false } = request.body
    const start = performance.now()
    const results = []
    try {
        for (const leg of legs) {
            const quantity = Number((total_budget / Number(leg.price) / legs.length).toFixed(4))
            const res = await fastify.inject({
                method: 'POST',
                url: '/order',
                payload: { ...leg, quantity, dry_run },
            })
            results.push(JSON.parse(res.payload))
        }
        return {
            success: results.every((r) => r.success),
            latency_ms: Math.round(performance.now() - start),
            legs: results,
        }
    } catch (err) {
        reply.status(400)
        return {
            success: false,
            latency_ms: Math.round(performance.now() - start),
            error: err.message,
        }
    }
})

fastify.post('/cancel/:order_id', async (request, reply) => {
    const { order_id } = request.params
    try {
        const result = await pmusRequest('POST', `/v1/order/${order_id}/cancel`, request.body || {})
        return { success: true, latency_ms: result.latencyMs, response: result.data }
    } catch (err) {
        reply.status(err.response?.status || 400)
        return { success: false, error: err.response?.data || err.message }
    }
})

fastify.post('/cancel-all', async (request, reply) => {
    try {
        const result = await pmusRequest('POST', '/v1/orders/open/cancel', request.body || {})
        return { success: true, latency_ms: result.latencyMs, response: result.data }
    } catch (err) {
        reply.status(err.response?.status || 400)
        return { success: false, error: err.response?.data || err.message }
    }
})

fastify.get('/orders/open', async (request) => {
    const result = await pmusRequest('GET', '/v1/orders/open', null, request.query || {})
    return { latency_ms: result.latencyMs, ...result.data }
})

const HOST = process.env.HOST || 'pii_0.0.0.0'
const PORT = process.env.PORT || 9000
fastify.listen({ port: PORT, host: HOST }, (err) => {
    if (err) {
        fastify.log.error(err)
        process.exit(1)
    }
})
