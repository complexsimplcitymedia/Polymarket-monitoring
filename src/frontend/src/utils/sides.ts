import { Market } from '../stores/marketStore'

export interface Side {
    label: string
    pct: number
}

export interface Sides {
    a: Side
    b: Side
    /** True when the market names its sides (teams, players) instead of Yes/No. */
    named: boolean
}

const isYesNo = (name: string): boolean => ['yes', 'no'].includes(name.trim().toLowerCase())

/**
 * The two sides of a market with a label and a percentage each. A game like "Florida vs. Missouri"
 * names its sides, so each team gets its own label and price. Everything else stays Yes/No.
 */
export function marketSides(market: Market): Sides {
    const o = market.outcomes
    if (o && o.length === 2 && !o.some((x) => isYesNo(x.name))) {
        const total = o[0].price + o[1].price
        // The two prices should add up to about 100; if they do not, keep the pair complementary.
        const a = total >= 97 && total <= 103 ? o[0].price : market.yes_percentage
        return {
            a: { label: o[0].name, pct: Math.min(Math.max(a, 0), 100) },
            b: { label: o[1].name, pct: Math.min(Math.max(100 - a, 0), 100) },
            named: true,
        }
    }
    const yes = Math.min(Math.max(market.yes_percentage, 0), 100)
    return { a: { label: 'Yes', pct: yes }, b: { label: 'No', pct: 100 - yes }, named: false }
}
