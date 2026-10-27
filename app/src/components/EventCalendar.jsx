import { calendarDays, dayKey, eventColour, parseEventDate } from '../lib/eventDates.js'

const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const colourLabels = { pink: 'Arts & culture', blue: 'Tech & academic', lime: 'Sports', gray: 'Other' }

export default function EventCalendar({ month, onMonthChange, selectedDay, onSelectDay, events }) {
  const today = dayKey(new Date())
  const dates = calendarDays(month)
  const byDay = new Map()
  for (const event of events) {
    const key = dayKey(parseEventDate(event.date))
    if (key) byDay.set(key, [...(byDay.get(key) || []), event])
  }
  const legendColours = [...new Set([...byDay.values()].flat().map((event) => eventColour(event.category)))]
  const label = new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric' }).format(month)

  return <div className="calendar" aria-label="Event calendar">
    <div className="calendar-head"><strong aria-live="polite">{label}</strong><div className="calendar-controls"><button type="button" aria-label="Previous month" onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>‹</button><button type="button" aria-label="Next month" onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>›</button></div></div>
    <div className="calendar-grid" key={dayKey(month)}>
      {weekdays.map((day) => <span className="calendar-weekday" key={day}>{day}</span>)}
      {dates.map((date) => {
        const key = dayKey(date)
        const dayEvents = byDay.get(key) || []
        const selected = selectedDay === key
        const outside = date.getMonth() !== month.getMonth()
        const categories = [...new Set(dayEvents.map((event) => eventColour(event.category)))].slice(0, 3)
        const fullDate = new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(date)
        return <button key={key} type="button" className={`calendar-day${outside ? ' is-outside' : ''}${key === today ? ' is-today' : ''}${selected ? ' is-selected' : ''}`} aria-label={`${fullDate}${dayEvents.length ? `, ${dayEvents.length} ${dayEvents.length === 1 ? 'event' : 'events'}` : ', no events'}`} aria-pressed={selected} onClick={() => onSelectDay(selected ? null : key, date)}><span>{date.getDate()}</span><span className="calendar-dots" aria-hidden="true">{categories.map((colour) => <i key={colour} className={`dot-${colour}`} />)}</span></button>
      })}
    </div>
    {legendColours.length > 0 && <div className="calendar-legend" aria-label="Event categories">{legendColours.map((colour) => <span key={colour}><i className={`dot-${colour}`} aria-hidden="true" />{colourLabels[colour]}</span>)}</div>}
  </div>
}
