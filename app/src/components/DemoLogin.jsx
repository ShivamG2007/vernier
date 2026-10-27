import { useState } from 'react'
import { Brand } from './ui.jsx'

export default function DemoLogin({ onSignIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [remember, setRemember] = useState(false)

  function submit(event) {
    event.preventDefault()
    if (!username || !password) {
      setError('Enter your username and password.')
      return
    }
    if (username === 'person1' && password === 'ABC123') {
      setPassword('')
      setError('')
      onSignIn(remember)
    } else {
      setError('That username or password didn’t match the demo credentials.')
    }
  }

  return <main className="login-screen">
    <div className="login-frame">
      <Brand className="login-brand" />
      <div className="login-panel">
        <span className="login-eyebrow">Campus companion · demo access</span>
        <h1>Welcome to Vernier.</h1>
        <p>Sign in to see the campus dashboard.</p>
        <form onSubmit={submit} autoComplete="off" noValidate>
          <label htmlFor="demo-username">Username</label>
          <input id="demo-username" name="username" type="text" autoComplete="off" value={username} onChange={(event) => { setUsername(event.target.value); setError('') }} required />
          <label htmlFor="demo-password">Password</label>
          <div className="password-field"><input id="demo-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="off" value={password} onChange={(event) => { setPassword(event.target.value); setError('') }} required /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((value) => !value)}>{showPassword ? 'Hide' : 'Show'}</button></div>
          <label className="remember-control"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />Remember me on this device</label>
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="login-submit" type="submit">Sign in <span aria-hidden="true">→</span></button>
        </form>
        <p className="login-note">Local demo sign-in only. No backend account is checked, and your password is not saved.</p>
      </div>
    </div>
  </main>
}
