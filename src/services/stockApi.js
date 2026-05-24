const API_KEY = import.meta.env.VITE_FMP_API_KEY
const BASE_URL = 'https://financialmodelingprep.com/api/v3'

const FALLBACK = {
  VICR:  { price: 67.43,  change:  0.81, changePercent:  1.21 },
  CDNS:  { price: 312.18, change:  2.51, changePercent:  0.81 },
  LSCC:  { price: 54.92,  change: -0.17, changePercent: -0.31 },
  SMR:   { price: 18.74,  change:  0.43, changePercent:  2.35 },
  CCJ:   { price: 52.31,  change: -0.89, changePercent: -1.67 },
  UEC:   { price: 8.47,   change:  0.12, changePercent:  1.44 },
  CBRS:  { price: 3.21,   change:  0.08, changePercent:  2.56 },
}

function makeFallback(tickers) {
  return Object.fromEntries(
    tickers.map(t => [t, FALLBACK[t] ?? { price: 0, change: 0, changePercent: 0 }])
  )
}

export async function fetchQuotes(tickers) {
  try {
    const symbols = tickers.join(',')
    const res = await fetch(`${BASE_URL}/quote/${symbols}?apikey=${API_KEY}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (!Array.isArray(data) || data.length === 0) throw new Error('Empty or invalid response')

    const result = makeFallback(tickers)
    for (const quote of data) {
      if (tickers.includes(quote.symbol)) {
        result[quote.symbol] = {
          price: quote.price,
          change: quote.change,
          changePercent: quote.changesPercentage,
        }
      }
    }
    return result
  } catch (err) {
    console.warn('fetchQuotes failed, using fallback:', err.message)
    return makeFallback(tickers)
  }
}
