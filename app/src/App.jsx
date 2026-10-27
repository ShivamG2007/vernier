import { useEffect, useState } from 'react'
import { Brand, ConnectionError, EmptyState, FilterTabs, Icon, LoadingState, SearchField } from './components/ui.jsx'
import DemoLogin from './components/DemoLogin.jsx'
import EventCalendar from './components/EventCalendar.jsx'
import { useRecords } from './hooks/useRecords.js'
import { dayKey, parseEventDate } from './lib/eventDates.js'

const divisions = [
  { id: 'lost-found', label: 'Lost & found', icon: 'search' },
  { id: 'events', label: 'Events & clubs', icon: 'calendar' },
  { id: 'marketplace', label: 'Marketplace', icon: 'bag' },
  { id: 'campus', label: 'Campus', icon: 'campus' },
  { id: 'profile', label: 'Profile & preferences', icon: 'user' },
]
const interests = ['sports', 'music', 'dance', 'theatre', 'culture', 'tech', 'academic', 'other']
const greetings = [
  'Hey, good to see you.',
  'What’s happening on campus?',
  'Ready for today?',
  'Your campus, your corner.',
  'Let’s make today count.',
  'Morning, campus.',
  'What’s new today?',
  'Good to have you here.',
  'Anything on your mind?',
  'Let’s see what’s happening.',
  'A good day to check in.',
  'Here’s your campus today.',
]
const sessionGreeting = greetings[Math.floor(Math.random() * greetings.length)]
const demoUser = 'person1'
const sessionKey = 'vernier-demo-session'
const preferencesKey = 'vernier-demo-preferences'

function readDemoSession() {
  try { if (localStorage.getItem(sessionKey) === demoUser) return { username: demoUser, remembered: true } } catch { /* Storage may be disabled. */ }
  return null
}
function storeDemoSession(remembered) {
  clearDemoSession()
  if (remembered) {
    try { localStorage.setItem(sessionKey, demoUser) } catch { /* Keep only the current in-memory demo session. */ }
  }
}
function clearDemoSession() {
  try { localStorage.removeItem(sessionKey) } catch { /* Nothing else to clear. */ }
  try { sessionStorage.removeItem(sessionKey) } catch { /* Nothing else to clear. */ }
}
function readDemoPreferences() {
  const defaults = { interests: [], level: 'all', reducedMotion: false }
  try {
    const stored = JSON.parse(localStorage.getItem(preferencesKey) || '{}')
    return {
      interests: Array.isArray(stored.interests) ? stored.interests.filter((item) => interests.includes(item)) : [],
      level: stored.level === 'major' ? 'major' : 'all',
      reducedMotion: stored.reducedMotion === true,
    }
  } catch { return defaults }
}

function route() {
  const id = window.location.hash.slice(1)
  return divisions.some((item) => item.id === id) ? id : null
}
function dateText(value) {
  return value ? String(value).replace('T', ' · ').slice(0, 16) : 'Time not recorded'
}
function freshness(value) {
  // Backend timestamps have no timezone, so never call an observation live.
  if (!value) return 'Time not recorded'
  return `Recorded ${dateText(value)}`
}
function itemName(row) {
  return [row.colour, row.item].filter(Boolean).join(' ') || 'Item not described'
}
function reportStatus(row) {
  if (row.status === 'claim_pending') return 'Claim pending, not verified'
  if (row.status === 'claimed') return row.cameraObservation ? 'Removed from shelf' : 'Marked claimed'
  if (row.status === 'unclaimed') return 'Unclaimed, collection needs desk review'
  return row.status === 'open' ? 'Open' : 'Status not available'
}
function Navigation({ open, mobile = false }) {
  const items = [{ id: 'home', label: 'Home', icon: 'home' }, ...divisions.filter((item) => mobile || item.id !== 'profile')]
  return <nav className={mobile ? 'mobile-nav' : 'side-nav'} aria-label={mobile ? 'Mobile navigation' : 'Main navigation'}>{items.map((item) => {
    const active = item.id === (open || 'home')
    return <a key={item.id} href={`#${item.id}`} aria-current={active ? 'page' : undefined} className={`nav-link ${active ? 'is-active' : ''}`}><Icon name={item.icon} size={21} /><span>{mobile ? ({ 'lost-found': 'Lost', marketplace: 'Market', profile: 'Profile', events: 'Events' }[item.id] || item.label) : item.label}</span></a>
  })}</nav>
}
function Header({ onSignOut }) {
  return <header className="topbar"><Brand href="#home" /><button className="topbar-sign-out" type="button" onClick={onSignOut}>Sign out</button></header>
}
function DataView({ state, children, empty = 'No records yet' }) {
  if (state.phase === 'loading') return <LoadingState />
  return <>
    {state.phase === 'error' && <ConnectionError offline={!navigator.onLine} stale={state.data.length > 0} />}
    {state.data.length ? children(state.data) : state.phase !== 'error' && <EmptyState title={empty} />}
    {state.updatedAt && <p className="updated-at">{state.phase === 'error' ? 'Last received' : 'Checked'} {new Date(state.updatedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</p>}
  </>
}
function CopyAction({ text, children, disabled = false }) {
  const [status, setStatus] = useState('idle')
  useEffect(() => setStatus('idle'), [text])
  async function copy() {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const field = document.createElement('textarea')
        field.value = text
        field.style.position = 'fixed'
        field.style.opacity = '0'
        document.body.appendChild(field)
        field.select()
        const copied = document.execCommand('copy')
        field.remove()
        if (!copied) throw new Error('Clipboard unavailable')
      }
      setStatus('copied')
    } catch { setStatus('error') }
  }
  return <span className="copy-action"><button type="button" disabled={disabled} onClick={copy}>{status === 'copied' ? 'Copied' : children}</button><span role="status" className="copy-feedback">{status === 'error' ? 'Could not copy. Select the text instead.' : status === 'copied' ? 'Ready to paste in WhatsApp.' : ''}</span></span>
}
function RecordList({ rows, render }) {
  return <div className="record-list">{rows.map(render)}</div>
}
function LostFound({ state }) {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('All')
  const openLost = useRecords('open_lost', '', kind === 'Open lost')
  const unclaimedFound = useRecords('unclaimed_found', '', kind === 'Unclaimed found')
  const selectedState = kind === 'Open lost' ? openLost : kind === 'Unclaimed found' ? unclaimedFound : state
  return <div className="division-content"><div className="content-heading"><div><h3>Lost something?</h3><p>Reports are sent through Vernier on WhatsApp. This dashboard cannot submit one yet.</p></div><div className="prompt-actions"><CopyAction text="I lost my [item] near [place]. It is [colour].">Copy lost report</CopyAction><CopyAction text="I found a [colour] [item] near [place].">Copy found report</CopyAction></div></div><div className="tool-row"><SearchField label="Search lost and found" placeholder="Search item or place" value={query} onChange={setQuery} /><FilterTabs label="Report type" options={['All', 'Open lost', 'Unclaimed found', 'Lost', 'Found']} value={kind} onChange={setKind} /></div><DataView state={selectedState} empty="No lost or found reports yet">{(rows) => {
    const matches = rows.filter((row) => {
      const matchesKind = kind === 'All' || kind === 'Lost' && row.kind === 'lost' || kind === 'Found' && row.kind === 'found' || kind === 'Open lost' && row.kind === 'lost' && row.status === 'open' || kind === 'Unclaimed found' && row.kind === 'found' && row.status === 'unclaimed'
      return matchesKind && `${row.item || ''} ${row.colour || ''} ${row.place || ''}`.toLowerCase().includes(query.toLowerCase().trim())
    })
    return matches.length ? <RecordList rows={matches} render={(row) => <details className="record-details" key={row.id}><summary><span className="record-title">{itemName(row)}</span><span className="record-meta">{row.kind === 'lost' ? 'Lost' : 'Found'} · {row.place || 'Place not recorded'}</span><Icon name="chevron" size={17} /></summary><div className="record-expanded"><span>Reported {dateText(row.created)}</span><span>{reportStatus(row)}</span><span>{row.cameraObservation ? 'Shelf observation' : 'Campus report'}</span><p>Ownership is not verified by this listing. Contact details are private.</p></div></details>} /> : <EmptyState title="No matches" description="Try another item or place." />
  }}</DataView></div>
}
function Events({ state, focusEventId }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')
  const [selected, setSelected] = useState(focusEventId)
  useEffect(() => setSelected(focusEventId), [focusEventId])
  const categories = ['All', ...new Set(state.data.map((row) => row.category).filter(Boolean))]
  const focused = state.data.find((row) => String(row.id) === String(selected))
  return <div className="division-content"><div className="content-heading"><h3>Events and clubs</h3></div>{focused && <div className="event-detail" role="region" aria-label="Event details"><span>{focused.category || 'Event'}{focused.major ? ' · Major' : ''}</span><h4>{focused.title || 'Untitled event'}</h4><p>{focused.date || 'Date not listed'} · {focused.venue || 'Venue not listed'}</p><button type="button" onClick={() => setSelected(null)}>Close details</button></div>}<div className="tool-row"><SearchField label="Search events" placeholder="Search event or venue" value={query} onChange={setQuery} /><FilterTabs label="Event category" options={categories} value={category} onChange={setCategory} /></div><DataView state={state} empty="No events posted yet">{(rows) => {
    const matches = rows.filter((row) => (category === 'All' || row.category === category) && `${row.title || ''} ${row.venue || ''}`.toLowerCase().includes(query.toLowerCase().trim()))
    return matches.length ? <RecordList rows={matches} render={(row) => <button className="record-row event-row event-row-button" type="button" key={row.id} onClick={() => setSelected(row.id)}><span className="event-row-main"><strong>{row.title || 'Untitled event'}</strong><span>{row.venue || 'Venue not listed'} · {row.date || 'Date not listed'}</span></span><small>{row.category || 'Other'}{row.major ? ' · Major' : ''}</small></button>} /> : <EmptyState title="No matching events" />
  }}</DataView></div>
}
function Marketplace({ state }) {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('All')
  return <div className="division-content"><div className="content-heading"><h3>Student listings</h3></div><div className="tool-row"><SearchField label="Search listings" placeholder="Search item" value={query} onChange={setQuery} /><FilterTabs label="Listing type" options={['All', 'For sale', 'Wanted']} value={kind} onChange={setKind} /></div><DataView state={state} empty="No listings posted yet">{(rows) => {
    const matches = rows.filter((row) => (kind === 'All' || row.kind === (kind === 'Wanted' ? 'buy' : 'sell')) && `${row.item || ''}`.toLowerCase().includes(query.toLowerCase().trim()))
    return matches.length ? <RecordList rows={matches} render={(row) => <div className="record-row listing-row" key={row.id}><div><strong>{row.item || 'Item not described'}</strong><span>{row.kind === 'buy' ? 'Wanted' : 'For sale'} · {row.status || 'open'}</span></div><b>{row.price || 'Price not listed'}</b></div>} /> : <EmptyState title="No matching listings" />
  }}</DataView><p className="footnote">Seller and buyer contacts stay private.</p></div>
}
function Campus({ machines }) {
  const [day, setDay] = useState(() => dayKey(new Date()))
  const bookings = useRecords('bookings', day)
  return <div className="division-content campus-content"><section><div className="content-heading"><h3>Machine observations</h3></div><DataView state={machines} empty="No machine observations yet">{(rows) => <RecordList rows={rows} render={(row) => <div className="record-row machine-row" key={row.id}><div><strong>{row.location || row.id || 'Machine'}</strong><span>{freshness(row.updated)}</span></div><small>{recentMachineReading(row) ? `Reported ${['free', 'in use'].includes(row.status) ? row.status : 'unknown'}` : 'Older observation'}</small></div>} />}</DataView><p className="footnote">These are last reported states, not live availability.</p></section><section><div className="content-heading"><h3>Room bookings</h3></div><label className="booking-day">Day <input type="date" value={day} onChange={(event) => setDay(event.target.value || dayKey(new Date()))} /></label><DataView state={bookings} empty="No local bookings for this day">{(rows) => <RecordList rows={rows} render={(row) => <div className="record-row" key={row.id}><div><strong>{row.room || 'Room'}</strong><span>{row.day || 'Day not listed'} · {row.start || '?'}–{row.end || '?'}</span></div></div>} />}</DataView><p className="footnote">Local booking records. Outlook is not connected.</p></section></div>
}
function Profile({ session, preferences, onPreferencesChange, onRememberChange, onSignOut }) {
  const selected = preferences.interests
  const toggle = (interest) => onPreferencesChange({ ...preferences, interests: selected.includes(interest) ? selected.filter((item) => item !== interest) : [...selected, interest] })
  return <div className="division-content profile-content">
    <section className="profile-section"><h3>Profile</h3><div className="profile-identity"><span className="profile-avatar" aria-hidden="true">P</span><div><strong>{session.username}</strong><span>Local demo account</span></div></div><p>No student contact or verified identity is connected to this account.</p></section>
    <section className="profile-section"><h3>General</h3><div className="profile-setting"><div><strong>Appearance</strong><span>Light theme</span></div><small>The dashboard currently supports light mode.</small></div><div className="profile-setting"><div><strong>Event alerts</strong><span>Local demo preference</span></div><div className="choice-pills" role="group" aria-label="Event alert level"><button type="button" aria-pressed={preferences.level === 'all'} className={preferences.level === 'all' ? 'is-selected' : ''} onClick={() => onPreferencesChange({ ...preferences, level: 'all' })}>All updates</button><button type="button" aria-pressed={preferences.level === 'major'} className={preferences.level === 'major' ? 'is-selected' : ''} onClick={() => onPreferencesChange({ ...preferences, level: 'major' })}>Major only</button></div></div><label className="profile-setting setting-check"><span><strong>Reduce motion</strong><small>Keep transitions to a minimum</small></span><input type="checkbox" checked={preferences.reducedMotion} onChange={(event) => onPreferencesChange({ ...preferences, reducedMotion: event.target.checked })} /></label></section>
    <section className="profile-section"><h3>Campus preferences</h3><p>Choose the events you care about.</p><div className="interest-grid" role="group" aria-label="Event interests">{interests.map((interest) => <button type="button" key={interest} aria-pressed={selected.includes(interest)} className={selected.includes(interest) ? 'is-selected' : ''} onClick={() => toggle(interest)}>{interest}<span aria-hidden="true">{selected.includes(interest) ? '✓' : '+'}</span></button>)}</div><p className="footnote">Selections stay in this browser. Alert delivery is not connected to this demo account.</p></section>
    <section className="profile-section"><h3>Account</h3><label className="profile-setting setting-check"><span><strong>Remember me</strong><small>{session.remembered ? 'Signed in across browser restarts on this device' : 'Signed in until you refresh or close this page'}</small></span><input type="checkbox" checked={session.remembered} onChange={(event) => onRememberChange(event.target.checked)} /></label><button className="profile-sign-out" type="button" onClick={onSignOut}>Sign out</button><p className="footnote">Demo sign-in only. This is not a secure campus account.</p></section>
  </div>
}
function TileData({ state, empty, children }) {
  if (state.phase === 'loading') return <span className="tile-status">Checking records…</span>
  if (!state.data.length) return <span className="tile-status">{state.phase === 'error' ? 'Updates unavailable' : empty}</span>
  return <>{state.phase === 'error' && <span className="tile-warning">Last received data</span>}{children(state.data)}</>
}
function StatPill({ value, label, tone }) {
  return <span className={`stat-pill stat-pill--${tone}`} aria-label={`${label}: ${value === null ? 'unavailable' : value}`}><strong>{value ?? '–'}</strong><span>{label}</span></span>
}
function recentMachineReading(row) {
  const stamp = row?.updated
  if (typeof stamp !== 'string' || !/(Z|[+-]\d{2}:?\d{2})$/.test(stamp)) return false
  const age = Date.now() - new Date(stamp).getTime()
  return Number.isFinite(age) && age >= 0 && age <= 5 * 60 * 1000
}
function Dashboard({ lost, events, listings, machines, bookings, onEventOpen, onViewEvents }) {
  const now = new Date()
  const [month, setMonth] = useState(() => new Date(now.getFullYear(), now.getMonth(), 1))
  const [selectedDay, setSelectedDay] = useState(null)
  const found = lost.data.find((row) => row.kind === 'found' && ['unclaimed', 'open'].includes(row.status))
  const eventRows = (selectedDay ? events.data.filter((event) => dayKey(parseEventDate(event.date)) === selectedDay) : events.data).slice(0, 3)
  const listingRows = listings.data.slice(0, 3)
  const machineRows = machines.data.slice(0, 2)
  const booking = bookings.data[0]
  const lostCount = lost.phase === 'ready' ? lost.data.filter((row) => row.kind === 'lost' && row.status === 'open').length : null
  const foundCount = lost.phase === 'ready' ? lost.data.filter((row) => row.kind === 'found' && ['unclaimed', 'open'].includes(row.status)).length : null
  const freshMachines = machines.data.filter(recentMachineReading)
  const inUseCount = machines.phase === 'ready' && freshMachines.length ? freshMachines.filter((row) => row.status === 'in use').length : null
  const freeCount = machines.phase === 'ready' && freshMachines.length ? freshMachines.filter((row) => row.status === 'free').length : null
  function changeMonth(next) { setMonth(next); setSelectedDay(null) }
  function selectDay(key, date) { setSelectedDay(key); setMonth(new Date(date.getFullYear(), date.getMonth(), 1)) }
  return <div className="dashboard-view"><div className="dashboard-heading"><div><h1>{sessionGreeting}</h1></div><span className="dashboard-date">{new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }).format(now)}</span></div><p className="dashboard-intro">Points of interest across campus</p><div className="bento-grid">
    <a className="bento-tile tile-lost" href="#lost-found"><div className="tile-stat-row"><span>Recent reports</span><div className="tile-stats"><StatPill value={lostCount} label="lost" tone="pink" /><StatPill value={foundCount} label="found" tone="pink" /></div></div><div className="lost-illustration" aria-hidden="true"><Icon name="search" size={80} /></div><div className="tile-lost-main"><h2>Lost & Found</h2><TileData state={lost} empty="No reports yet">{() => found ? <div className="tile-feature-record"><strong>{itemName(found)}</strong><span>{found.place || 'Place not recorded'} · {dateText(found.created)}</span></div> : <span className="tile-status">No found items yet</span>}</TileData></div><span className="tile-link">Browse reports <Icon name="arrow" size={17} /></span></a>
    <section className="bento-tile tile-events" aria-labelledby="events-tile-title"><a className="tile-cover" href="#events" onClick={onViewEvents} aria-label="Open events and clubs" /><div className="events-overview"><div className="tile-top"></div><h2 id="events-tile-title">Pinboard</h2><p className="tile-hint">{selectedDay ? `Events on ${new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(new Date(`${selectedDay}T12:00:00`))}` : 'Latest event posts'}</p><TileData state={events} empty="No events posted yet">{() => eventRows.length ? <div className="tile-event-list" key={selectedDay || 'latest'}>{eventRows.map((event) => <button type="button" key={event.id} onClick={() => onEventOpen(event.id)}><span>{event.date || 'Date not listed'}</span><strong>{event.title || 'Untitled event'}</strong><small>{event.venue || 'Venue not listed'}</small></button>)}</div> : <span className="tile-status">No events on this date</span>}</TileData><a className="tile-link event-link" href="#events" onClick={onViewEvents}>See events <Icon name="arrow" size={17} /></a></div><EventCalendar month={month} onMonthChange={changeMonth} selectedDay={selectedDay} onSelectDay={selectDay} events={events.data} /></section>
    <a className="bento-tile tile-market" href="#marketplace"><span className="tile-ornament" aria-hidden="true"><Icon name="bag" size={64} /></span><div><h2>Earn or Spend $</h2><p className="tile-hint">Buy, sell or exchange on campus.</p></div><TileData state={listings} empty="No listings yet">{() => <div className="market-strip">{listingRows.map((row) => <div key={row.id}><strong>{row.item || 'Item not described'}</strong><span>{row.kind === 'buy' ? 'Wanted' : 'For sale'}</span><b>{row.price || 'Price not listed'}</b></div>)}</div>}</TileData><span className="tile-link">Browse listings <Icon name="arrow" size={17} /></span></a>
    <a className="bento-tile tile-laundry" href="#campus"><span className="tile-ornament tile-machine-art" aria-hidden="true"><Icon name="washer" size={68} /></span><div className="tile-stat-row"><span>Recent reports</span><div className="tile-stats"><StatPill value={inUseCount} label="in use" tone="blue" /><StatPill value={freeCount} label="free" tone="lime" /></div></div><div><h2>Machine reports</h2><p className="tile-hint">Last recorded observations.</p></div><TileData state={machines} empty="No observations yet">{() => <div className="machine-strip">{machineRows.map((row) => <div key={row.id}><span className={`machine-indicator${recentMachineReading(row) && row.status === 'free' ? ' is-recent-free' : ''}`} /><strong>{!recentMachineReading(row) ? 'Older report' : ['free', 'in use'].includes(row.status) ? `Reported ${row.status}` : 'Status unknown'}</strong><small>{row.location || row.id || 'Machine'} · {freshness(row.updated)}</small></div>)}</div>}</TileData><span className="tile-link">View machines <Icon name="arrow" size={17} /></span></a>
    <a className="bento-tile tile-rooms" href="#campus"><span className="tile-ornament" aria-hidden="true"><Icon name="campus" size={70} /></span><div><h2>Ticketmaster</h2><p className="tile-hint">View local room bookings</p></div><TileData state={bookings} empty="No bookings yet">{() => <div className="room-record"><strong>{booking.room || 'Room'}</strong><span>{booking.day || 'Day not listed'} · {booking.start || '?'}–{booking.end || '?'}</span></div>}</TileData><span className="tile-link">View bookings <Icon name="arrow" size={17} /></span></a>
    <div className="bento-tile tile-action"><div className="action-inline"><div><h2>Wanna talk on WhatsApp?</h2><p>Open WhatsApp, then choose your Vernier chat.</p></div><a className="tile-link" href="https://web.whatsapp.com/" target="_blank" rel="noopener noreferrer" aria-label="Open WhatsApp Web in a new tab">Chat now <Icon name="arrow" size={17} /></a></div></div>
    <a className="bento-tile tile-profile" href="#profile"><div><h2>Event alerts</h2><p>Choose interests and alert level.</p></div><span className="tile-link">Set preferences <Icon name="arrow" size={17} /></span></a>
  </div><p className="dashboard-disclaimer">Records refresh when the backend is connected. Machine readings are observations; room bookings are local records.</p></div>
}
function DetailView({ page, content }) {
  const titles = { 'lost-found': 'Lost & found', events: 'Events & clubs', marketplace: 'Marketplace', campus: 'Campus', profile: 'Profile & preferences' }
  return <div className="detail-view" key={page}><a className="back-link" href="#home"><Icon name="arrow" size={17} /> Back to dashboard</a><div className="detail-heading"><h1>{titles[page]}</h1></div>{content}</div>
}
function DashboardApp({ session, onRememberChange, onSignOut }) {
  const [open, setOpen] = useState(route)
  const [focusedEventId, setFocusedEventId] = useState(null)
  const [preferences, setPreferences] = useState(readDemoPreferences)
  const lost = useRecords('lost_found')
  const events = useRecords('events')
  const listings = useRecords('listings')
  const machines = useRecords('machines')
  const bookings = useRecords('bookings', dayKey(new Date()), open !== 'campus')
  useEffect(() => {
    try { localStorage.setItem(preferencesKey, JSON.stringify(preferences)) } catch { /* Browser storage is optional. */ }
  }, [preferences])
  useEffect(() => {
    const onHashChange = () => {
      setOpen(route())
      window.scrollTo({ top: 0, behavior: 'instant' })
      document.getElementById('main')?.scrollTo({ top: 0, behavior: 'instant' })
      requestAnimationFrame(() => document.getElementById('main')?.focus({ preventScroll: true }))
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  const content = {
    'lost-found': <LostFound state={lost} />,
    events: <Events state={events} focusEventId={focusedEventId} />,
    marketplace: <Marketplace state={listings} />,
    campus: <Campus machines={machines} />,
    profile: <Profile session={session} preferences={preferences} onPreferencesChange={setPreferences} onRememberChange={onRememberChange} onSignOut={onSignOut} />,
  }
  function openEvent(id) { setFocusedEventId(id); window.location.hash = 'events' }
  return <><a className="skip-link" href="#main">Skip to content</a><Header onSignOut={onSignOut} /><div className={`app-layout${preferences.reducedMotion ? ' is-reduced-motion' : ''}`}><aside className="sidebar"><Brand href="#home" className="sidebar-brand" /><Navigation open={open} /><a className={`sidebar-profile ${open === 'profile' ? 'is-active' : ''}`} href="#profile"><Icon name="user" size={21} /><span>Profile & preferences</span><Icon name="arrow" size={15} /></a><button className="sidebar-sign-out" type="button" onClick={onSignOut}>Sign out</button></aside><main id="main" tabIndex="-1" className="main-content"><div className="content-wrap">{open ? <DetailView page={open} content={content[open]} /> : <Dashboard lost={lost} events={events} listings={listings} machines={machines} bookings={bookings} onEventOpen={openEvent} onViewEvents={() => setFocusedEventId(null)} />}<footer className="footer"><span>Vernier · Precision for campus life</span><span>WhatsApp is the main student interface</span></footer></div></main></div><Navigation open={open} mobile /></>
}
function App() {
  const [session, setSession] = useState(readDemoSession)
  function signIn(remembered) {
    storeDemoSession(remembered)
    setSession({ username: demoUser, remembered })
  }
  function changeRemembered(remembered) {
    storeDemoSession(remembered)
    setSession({ username: demoUser, remembered })
  }
  function signOut() {
    clearDemoSession()
    window.location.hash = 'home'
    setSession(null)
  }
  return session ? <DashboardApp session={session} onRememberChange={changeRemembered} onSignOut={signOut} /> : <DemoLogin onSignIn={signIn} />
}
export default App
