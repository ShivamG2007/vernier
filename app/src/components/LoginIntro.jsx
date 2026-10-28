import { useEffect, useRef, useState } from 'react'

const vertex = `attribute vec2 position;
varying vec2 uv;
void main() { uv = (position + 1.0) * 0.5; gl_Position = vec4(position, 0.0, 1.0); }`
const fragment = `precision mediump float;
varying vec2 uv;
uniform sampler2D frame;
void main() {
  vec3 color = texture2D(frame, vec2(uv.x, 1.0 - uv.y)).rgb;
  float greenExcess = color.g - max(color.r, color.b);
  float greenAlpha = 1.0 - smoothstep(0.08, 0.4, greenExcess);
  float darkAlpha = smoothstep(0.015, 0.12, max(max(color.r, color.g), color.b));
  float alpha = greenAlpha * darkAlpha;
  vec3 foreground = color;
  foreground.g = min(foreground.g, max(foreground.r, foreground.b) + 0.025);
  gl_FragColor = vec4(foreground, alpha);
}`

function shader(gl, type, source) {
  const result = gl.createShader(type)
  gl.shaderSource(result, source)
  gl.compileShader(result)
  if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) throw new Error('Intro shader unavailable')
  return result
}

function makeRenderer(canvas, video) {
  const gl = canvas.getContext('webgl', { alpha: true, antialias: false, premultipliedAlpha: true })
  if (!gl) throw new Error('WebGL unavailable')
  const program = gl.createProgram()
  const vertexShader = shader(gl, gl.VERTEX_SHADER, vertex)
  const fragmentShader = shader(gl, gl.FRAGMENT_SHADER, fragment)
  gl.attachShader(program, vertexShader)
  gl.attachShader(program, fragmentShader)
  gl.linkProgram(program)
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Intro program unavailable')
  const buffer = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
  gl.useProgram(program)
  const position = gl.getAttribLocation(program, 'position')
  gl.enableVertexAttribArray(position)
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)
  const texture = gl.createTexture()
  gl.bindTexture(gl.TEXTURE_2D, texture)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)

  gl.uniform1i(gl.getUniformLocation(program, 'frame'), 0)
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  gl.viewport(0, 0, canvas.width, canvas.height)
  return {
    draw() {
      gl.bindTexture(gl.TEXTURE_2D, texture)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, video)
      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
      if (gl.getError() !== gl.NO_ERROR) throw new Error('Intro frame rendering failed')
    },
    dispose() {
      gl.deleteTexture(texture)
      gl.deleteBuffer(buffer)
      gl.deleteProgram(program)
      gl.deleteShader(vertexShader)
      gl.deleteShader(fragmentShader)
    },
  }
}

export default function LoginIntro({ onDone, reduceMotion }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [phase, setPhase] = useState('waiting')

  useEffect(() => {
    const video = videoRef.current
    const canvas = canvasRef.current
    let renderer
    let frameId
    let startTimer
    let endTimer
    let exitTimer
    let finished = false
    let started = false
    const reduced = reduceMotion || window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) { onDone(); return }

    function finish() {
      if (finished) return
      finished = true
      clearTimeout(startTimer)
      clearTimeout(endTimer)
      if (frameId !== undefined) cancelAnimationFrame(frameId)
      video.pause()
      setPhase('leaving')
      exitTimer = setTimeout(onDone, 400)
    }
    function fail() { finish() }
    function draw() {
      if (finished || video.paused || document.hidden) return
      try { renderer.draw() } catch { fail(); return }
      frameId = requestAnimationFrame(draw)
    }
    async function start() {
      if (started || finished || !video.videoWidth || !video.videoHeight) return
      started = true
      try {
        video.currentTime = 0
        renderer = makeRenderer(canvas, video)
        renderer.draw()
        clearTimeout(startTimer)
        setPhase('playing')
        // Arm the watchdog before play(): autoplay promises can remain pending.
        endTimer = setTimeout(fail, (Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 4) * 1000 + 2000)
        await video.play()
        if (finished) return
        draw()
      } catch { fail() }
    }
    function visibility() {
      if (document.hidden) { video.pause(); cancelAnimationFrame(frameId) }
      else if (started && !finished && video.paused) video.play().then(draw).catch(fail)
    }
    video.addEventListener('canplay', start)
    video.addEventListener('ended', finish)
    video.addEventListener('error', fail)
    const contextLost = (event) => { event.preventDefault(); fail() }
    canvas.addEventListener('webglcontextlost', contextLost)
    document.addEventListener('visibilitychange', visibility)
    startTimer = setTimeout(fail, 3500)
    try { video.load() } catch { fail() }
    if (video.readyState >= 3) start()
    return () => {
      finished = true
      clearTimeout(startTimer)
      clearTimeout(endTimer)
      clearTimeout(exitTimer)
      cancelAnimationFrame(frameId)
      video.pause()
      video.removeEventListener('canplay', start)
      video.removeEventListener('ended', finish)
      video.removeEventListener('error', fail)
      canvas.removeEventListener('webglcontextlost', contextLost)
      document.removeEventListener('visibilitychange', visibility)
      renderer?.dispose()
    }
  }, [onDone, reduceMotion])

  return <div className={`login-intro login-intro--${phase}`} role="status" aria-label="Vernier is opening">
    <img className="login-intro-fallback" src="/vernier-mark.png" alt="" aria-hidden="true" />
    <canvas ref={canvasRef} aria-hidden="true" />
    <video ref={videoRef} src="/assets/vernier-intro.mp4" preload="auto" playsInline muted aria-hidden="true" />
  </div>
}
