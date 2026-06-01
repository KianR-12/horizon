#!/usr/bin/env node
/**
 * tracker.js — Polymarket Smart Money Tracker
 *
 * Features:
 *   • Dollar-weighted signals  — $500k on YES beats 10 × $200 votes
 *   • Entry price tracking     — avg entry vs current price shows signal age
 *   • History log              — every run appended to history.ndjson
 *   • Diff alerts              — only NEW / INCREASED / GONE signals printed
 *
 * Usage:
 *   node tracker.js              # min 2 traders on one side
 *   node tracker.js --min 5      # stricter filter
 *
 * Cron (every 4 h):
 *   0 *\/4 * * * cd /Users/kianrajabtavousi/horizon && node tracker.js >> tracker.log 2>&1
 */

import { writeFileSync, appendFileSync, readFileSync, existsSync } from 'fs'
import { parseArgs } from 'util'

// ─── Config ────────────────────────────────────────────────────────────────

const DATA_API  = 'https://data-api.polymarket.com'
const TOP_N     = 50
const DELAY_MS  = 120
const HEADERS   = { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' }
const RESULTS   = 'results.json'
const HISTORY   = 'history.ndjson'

// ─── CLI ───────────────────────────────────────────────────────────────────

const { values: flags } = parseArgs({
  args: process.argv.slice(2),
  options: { min: { type: 'string', default: '2' } },
  strict: false,
})
const MIN_OVERLAP = parseInt(flags.min, 10)

// ─── Helpers ───────────────────────────────────────────────────────────────

async function get(url) {
  const res = await fetch(url, { headers: HEADERS })
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${url}`)
  return res.json()
}

const sleep = ms => new Promise(r => setTimeout(r, ms))

function fmtUsd(n) {
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(2) + 'M'
  if (n >= 1e3) return '$' + (n / 1e3).toFixed(1) + 'k'
  return '$' + n.toFixed(0)
}

function fmtPct(n) {
  if (n == null || isNaN(n)) return '  —  '
  const sign = n >= 0 ? '+' : ''
  return sign + (n * 100).toFixed(0) + '%'
}

// Consensus bar driven by dollar weight, not raw count
function bar(yesUsd, noUsd) {
  const total = yesUsd + noUsd
  if (total === 0) return '─────────────────────'
  const w      = 21
  const yesLen = Math.round((yesUsd / total) * w)
  return '█'.repeat(yesLen) + '░'.repeat(w - yesLen)
}

// Weighted average: Σ(weight_i × value_i) / Σ(weight_i)
function wavg(holders, valueKey, weightKey) {
  let num = 0, den = 0
  for (const h of holders) {
    const w = h[weightKey] || 0
    const v = h[valueKey]  || 0
    num += w * v
    den += w
  }
  return den > 0 ? num / den : null
}

// ─── Step 1: Leaderboard ──────────────────────────────────────────────────

async function fetchLeaderboard() {
  process.stdout.write(`Fetching top ${TOP_N} traders by 30-day PnL…`)
  const data = await get(`${DATA_API}/v1/leaderboard?limit=${TOP_N}&window=1m`)
  console.log(` ${data.length} loaded`)
  return data.map(t => ({
    rank:   parseInt(t.rank, 10),
    wallet: t.proxyWallet,
    name:   t.userName || t.proxyWallet.slice(0, 10) + '…',
    pnl:    t.pnl,
  }))
}

// ─── Step 2: Positions ────────────────────────────────────────────────────

async function fetchAllPositions(traders) {
  const results = []
  let loaded = 0, empty = 0, errors = 0

  for (let i = 0; i < traders.length; i++) {
    const { wallet, rank, name } = traders[i]
    process.stdout.write(`\r  Wallet ${i + 1}/${traders.length}  rank ${rank} — ${name.slice(0, 24)}        `)

    try {
      const positions = await get(`${DATA_API}/positions?user=${wallet}&sizeThreshold=.01`)
      if (positions.length > 0) { results.push({ wallet, rank, name, positions }); loaded++ }
      else empty++
    } catch { errors++ }

    if (i < traders.length - 1) await sleep(DELAY_MS)
  }

  console.log(`\n  ${loaded} with positions  (${empty} empty  ${errors} errors)`)
  return results
}

// ─── Step 3: Aggregate ────────────────────────────────────────────────────
//
// Per holder we store:
//   size     — number of shares held
//   usd      — current dollar value  (size × curPrice, or currentValue if present)
//   avgPrice — their average entry price
//   curPrice — current market price at time of snapshot

function aggregate(walletData) {
  const markets = new Map()

  for (const { wallet, rank, name, positions } of walletData) {
    for (const pos of positions) {
      if (!pos.conditionId || !pos.title) continue

      const key = pos.conditionId
      if (!markets.has(key)) {
        markets.set(key, {
          title:      pos.title,
          conditionId: pos.conditionId,
          slug:       pos.slug,
          curPrice:   pos.curPrice,
          yesHolders: [],
          noHolders:  [],
        })
      }

      const mkt    = markets.get(key)
      const isYes  = pos.outcome?.toLowerCase() === 'yes' || pos.outcomeIndex === 0
      const size   = pos.size      || 0
      const usd    = pos.currentValue != null
                       ? pos.currentValue
                       : size * (pos.curPrice || 0)
      const entry  = pos.avgPrice  || pos.curPrice || 0

      const holder = { wallet, rank, name, size, usd, avgPrice: entry, curPrice: pos.curPrice }

      if (isYes) mkt.yesHolders.push(holder)
      else        mkt.noHolders.push(holder)

      mkt.curPrice = pos.curPrice   // keep freshest price
    }
  }

  return markets
}

// ─── Step 4: Enrich + sort ────────────────────────────────────────────────

function enrich(markets, minOverlap) {
  const rows = []

  for (const m of markets.values()) {
    const yesCount = m.yesHolders.length
    const noCount  = m.noHolders.length
    const overlap  = Math.max(yesCount, noCount)
    if (overlap < minOverlap) continue

    const yesUsd = m.yesHolders.reduce((s, h) => s + h.usd, 0)
    const noUsd  = m.noHolders.reduce((s, h) => s + h.usd, 0)

    // Weighted avg entry on each side (weight = usd size)
    const yesEntry = wavg(m.yesHolders, 'avgPrice', 'usd')
    const noEntry  = wavg(m.noHolders,  'avgPrice', 'usd')

    const dominantSide = yesUsd >= noUsd ? 'YES' : 'NO'
    const dominantUsd  = Math.max(yesUsd, noUsd)
    const dominantEntry = dominantSide === 'YES' ? yesEntry : noEntry
    const drift         = dominantEntry != null ? m.curPrice - dominantEntry : null

    rows.push({
      ...m,
      yesCount, noCount, overlap,
      yesUsd, noUsd,
      yesEntry, noEntry,
      dominantSide, dominantUsd, dominantEntry, drift,
    })
  }

  // Sort by total dollar weight on dominant side — big money first
  rows.sort((a, b) => b.dominantUsd - a.dominantUsd)
  return rows
}

// ─── Step 5: Render ───────────────────────────────────────────────────────

function render(rows) {
  if (rows.length === 0) {
    console.log(`\n  No markets with ≥${MIN_OVERLAP} smart-money traders on one side.\n`)
    return
  }

  // Column widths — title expands to fit longest market name
  const maxTitle = Math.max(...rows.map(r => r.title.length), 6)
  const W = { i: 3, title: maxTitle, yc: 4, yUsd: 8, nc: 4, nUsd: 8, price: 6, entry: 6, drift: 6, bar: 21 }
  const hr = '─'.repeat(Object.values(W).reduce((a, b) => a + b) + Object.keys(W).length * 2 + 2)
  const indent = '  ' + ' '.repeat(W.i + 2)  // align URL under title column

  console.log()
  console.log(`  SMART MONEY TRACKER — top ${TOP_N} traders, 30-day PnL  |  min overlap: ${MIN_OVERLAP}  |  ${new Date().toLocaleString()}`)
  console.log(`  Markets shown: ${rows.length}   Sorted by: dominant-side dollar weight`)
  console.log()
  console.log('  ' + hr)
  console.log(
    '  ' +
    '#'.padEnd(W.i) + '  ' +
    'Market'.padEnd(W.title) + '  ' +
    'YESn'.padStart(W.yc) + '  ' +
    'YES$'.padStart(W.yUsd) + '  ' +
    'NOn'.padStart(W.nc) + '  ' +
    'NO$'.padStart(W.nUsd) + '  ' +
    'Now'.padStart(W.price) + '  ' +
    'Entry'.padStart(W.entry) + '  ' +
    'Drift'.padStart(W.drift) + '  ' +
    'Consensus (YES→NO)'
  )
  console.log('  ' + hr)

  for (let i = 0; i < rows.length; i++) {
    const m     = rows[i]
    const price = m.curPrice != null ? (m.curPrice * 100).toFixed(0) + '%' : '—'
    const entry = m.dominantEntry != null ? (m.dominantEntry * 100).toFixed(0) + '%' : '—'
    const drift = m.drift != null ? fmtPct(m.drift) : '—'
    const side  = m.dominantSide

    console.log(
      '  ' +
      String(i + 1).padEnd(W.i) + '  ' +
      m.title.padEnd(W.title) + '  ' +
      String(m.yesCount).padStart(W.yc) + '  ' +
      fmtUsd(m.yesUsd).padStart(W.yUsd) + '  ' +
      String(m.noCount).padStart(W.nc) + '  ' +
      fmtUsd(m.noUsd).padStart(W.nUsd) + '  ' +
      price.padStart(W.price) + '  ' +
      entry.padStart(W.entry) + '  ' +
      drift.padStart(W.drift) + '  ' +
      bar(m.yesUsd, m.noUsd) + `  ${side}`
    )
    if (m.slug) console.log(indent + `https://polymarket.com/event/${m.slug}`)
  }

  console.log('  ' + hr)
  console.log()
}

// ─── Step 6: Diff against previous run ───────────────────────────────────

function diffAndAlert(rows) {
  if (!existsSync(RESULTS)) return   // first run — nothing to diff

  let prev
  try {
    prev = JSON.parse(readFileSync(RESULTS, 'utf8'))
  } catch {
    return   // corrupted previous file — skip diff
  }

  const prevMap = new Map(prev.markets.map(m => [m.conditionId, m]))
  const currMap = new Map(rows.map(m => [m.conditionId, m]))

  const newSignals     = []
  const increased      = []
  const gone           = []

  for (const [id, m] of currMap) {
    if (!prevMap.has(id)) {
      newSignals.push(m)
    } else {
      const p = prevMap.get(id)
      if (m.overlap > p.overlap) increased.push({ curr: m, prev: p })
    }
  }

  for (const [id, p] of prevMap) {
    if (!currMap.has(id)) gone.push(p)
  }

  if (newSignals.length + increased.length + gone.length === 0) {
    console.log('  No changes since last run.\n')
    return
  }

  console.log(`  ── DIFF vs last run ─────────────────────────────────────────`)

  for (const m of newSignals) {
    const side  = m.dominantSide
    const count = side === 'YES' ? m.yesCount : m.noCount
    const usd   = side === 'YES' ? m.yesUsd   : m.noUsd
    const entry = m.dominantEntry != null ? ` entry ${(m.dominantEntry * 100).toFixed(0)}%` : ''
    const now   = m.curPrice   != null ? ` now ${(m.curPrice * 100).toFixed(0)}%` : ''
    console.log(`  🆕 NEW    ${m.title.slice(0, 52).padEnd(52)}  ${side} ×${count} ${fmtUsd(usd)}${entry}${now}`)
  }

  for (const { curr, prev } of increased) {
    const side = curr.dominantSide
    const cUsd = side === 'YES' ? curr.yesUsd : curr.noUsd
    console.log(`  📈 MORE   ${curr.title.slice(0, 52).padEnd(52)}  ${side} ${prev.overlap}→${curr.overlap} traders  ${fmtUsd(cUsd)}`)
  }

  for (const m of gone) {
    const side  = m.dominantSide
    const entry = m.dominantEntry != null ? ` entry ${(m.dominantEntry * 100).toFixed(0)}%` : ''
    console.log(`  📉 GONE   ${m.title.slice(0, 52).padEnd(52)}  was ${side} ×${m.overlap}${entry}`)
  }

  console.log()
}

// ─── Step 7: Save ─────────────────────────────────────────────────────────

function save(rows, traders, walletData) {
  const snapshot = {
    timestamp:            new Date().toISOString(),
    window:               '30d',
    tradersTotal:         traders.length,
    tradersWithPositions: walletData.length,
    minOverlap:           MIN_OVERLAP,
    markets: rows.map(m => ({
      title:          m.title,
      conditionId:    m.conditionId,
      slug:           m.slug,
      curPrice:       m.curPrice,
      yesCount:       m.yesCount,
      noCount:        m.noCount,
      yesUsd:         Math.round(m.yesUsd),
      noUsd:          Math.round(m.noUsd),
      overlap:        m.overlap,
      dominantSide:   m.dominantSide,
      dominantUsd:    Math.round(m.dominantUsd),
      dominantEntry:  m.dominantEntry,
      drift:          m.drift,
      yesHolders: m.yesHolders.map(h => ({ rank: h.rank, name: h.name, usd: Math.round(h.usd), avgPrice: h.avgPrice })),
      noHolders:  m.noHolders.map(h =>  ({ rank: h.rank, name: h.name, usd: Math.round(h.usd), avgPrice: h.avgPrice })),
    })),
  }

  writeFileSync(RESULTS, JSON.stringify(snapshot, null, 2))
  appendFileSync(HISTORY, JSON.stringify(snapshot) + '\n')

  const histLines = existsSync(HISTORY)
    ? readFileSync(HISTORY, 'utf8').trim().split('\n').length
    : 1
  console.log(`  Saved ${rows.length} markets → ${RESULTS}   (${histLines} snapshots in ${HISTORY})`)
}

// ─── Main ─────────────────────────────────────────────────────────────────

async function main() {
  console.log()
  try {
    const traders    = await fetchLeaderboard()
    const walletData = await fetchAllPositions(traders)
    const markets    = aggregate(walletData)
    const rows       = enrich(markets, MIN_OVERLAP)

    diffAndAlert(rows)
    render(rows)
    save(rows, traders, walletData)
  } catch (err) {
    console.error('\nFatal:', err.message)
    process.exit(1)
  }
}

main()
