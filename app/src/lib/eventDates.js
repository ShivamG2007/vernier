const months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

function validDate(year, month, day) {
  const date = new Date(year, month - 1, day)
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : null
}

// The backend stores an extracted free-text date. Only unambiguous dates get calendar markers.
export function parseEventDate(value) {
  if (typeof value !== 'string') return null
  const text = value.trim().replace(/^(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?),?\s+/i, '')
  let match = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\D|$)/)
  if (match) return validDate(Number(match[1]), Number(match[2]), Number(match[3]))

  match = text.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\D|$)/)
  if (match) return validDate(Number(match[3]), Number(match[2]), Number(match[1]))

  match = text.match(/^(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+),?\s+(\d{4})(?:\D|$)/i)
  if (match) {
    const month = months.indexOf(match[2].slice(0, 3).toLowerCase()) + 1
    return month ? validDate(Number(match[3]), month, Number(match[1])) : null
  }

  match = text.match(/^([a-z]+)\s+(\d{1,2}),?\s+(\d{4})(?:\D|$)/i)
  if (match) {
    const month = months.indexOf(match[1].slice(0, 3).toLowerCase()) + 1
    return month ? validDate(Number(match[3]), month, Number(match[2])) : null
  }
  return null
}

export function dayKey(date) {
  if (!date) return null
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

export function calendarDays(month) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1)
  const mondayOffset = (first.getDay() + 6) % 7
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  const count = Math.max(35, Math.ceil((mondayOffset + daysInMonth) / 7) * 7)
  return Array.from({ length: count }, (_, index) => new Date(month.getFullYear(), month.getMonth(), index + 1 - mondayOffset))
}

export function eventColour(category) {
  if (['tech', 'academic'].includes(category)) return 'blue'
  if (category === 'sports') return 'lime'
  if (['music', 'dance', 'theatre', 'culture'].includes(category)) return 'pink'
  return 'gray'
}
