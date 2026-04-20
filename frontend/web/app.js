/* ============================================================ */
/* PTSD-Ai web client                                          */
/* Connects to LiveKit room, streams mic, plays agent audio    */
/* ============================================================ */

const TOKEN_ENDPOINT = '/api/livekit-token';  // backend issues short-lived JWTs

// ---------- DOM ----------
const idleScreen   = document.getElementById('idle');
const callScreen   = document.getElementById('call');
const callBtn      = document.getElementById('callBtn');
const hangupBtn    = document.getElementById('hangupBtn');
const statusDot    = document.getElementById('statusDot');
const statusText   = document.getElementById('statusText');
const timerEl      = document.getElementById('timer');
const canvas       = document.getElementById('visualizer');

// ---------- State ----------
let room = null;
let timerStart = 0;
let timerInterval = null;
let audioCtx = null;
let analyser = null;
let micSource = null;
let agentSource = null;

// ---------- Helpers ----------
function setStatus(state, text) {
  statusDot.className = `status-dot ${state}`;
  statusText.textContent = text;
}

function showScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(name).classList.add('active');
}

function startTimer() {
  timerStart = Date.now();
  const tick = () => {
    const elapsed = Math.floor((Date.now() - timerStart) / 1000);
    const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
    const s = String(elapsed % 60).padStart(2, '0');
    timerEl.textContent = `${m}:${s}`;
  };
  tick();
  timerInterval = setInterval(tick, 1000);
}

function stopTimer() {
  clearInterval(timerInterval);
  timerEl.textContent = '00:00';
}

// ---------- Visualizer ----------
function initVisualizer() {
  const dpr = window.devicePixelRatio || 1;
  canvas.width  = canvas.clientWidth  * dpr;
  canvas.height = canvas.clientHeight * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  const bars = 48;
  const gap = 3;
  const barWidth = (w - gap * (bars - 1)) / bars;

  function draw() {
    if (!analyser) {
      requestAnimationFrame(draw);
      return;
    }
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);

    ctx.clearRect(0, 0, w, h);
    const isAgent = statusDot.classList.contains('speaking');
    const color = isAgent ? '#6ba4ff' : '#4ade80';

    for (let i = 0; i < bars; i++) {
      const idx = Math.floor((i / bars) * data.length * 0.6);
      const v = data[idx] / 255;
      const barH = Math.max(3, v * h * 0.85);
      const x = i * (barWidth + gap);
      const y = (h - barH) / 2;

      const grad = ctx.createLinearGradient(0, y, 0, y + barH);
      grad.addColorStop(0, color);
      grad.addColorStop(1, color + '88');
      ctx.fillStyle = grad;
      roundRect(ctx, x, y, barWidth, barH, barWidth / 2);
      ctx.fill();
    }
    requestAnimationFrame(draw);
  }
  draw();
}

function roundRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y,     x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x,     y + h, r);
  ctx.arcTo(x,     y + h, x,     y,     r);
  ctx.arcTo(x,     y,     x + w, y,     r);
  ctx.closePath();
}

function attachAnalyser(stream, source) {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (!analyser) {
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.7;
  }
  source = audioCtx.createMediaStreamSource(stream);
  source.connect(analyser);
  return source;
}

// ---------- Token ----------
async function fetchToken() {
  try {
    const resp = await fetch(TOKEN_ENDPOINT, { method: 'POST' });
    if (!resp.ok) throw new Error('Token endpoint failed');
    return await resp.json();   // { token, url }
  } catch (e) {
    // Local dev fallback - read from query string
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const url   = params.get('url');
    if (token && url) return { token, url };
    throw new Error('No token available. Set up /api/livekit-token or pass ?token=&url= for dev.');
  }
}

// ---------- Call lifecycle ----------
async function startCall() {
  callBtn.disabled = true;
  setStatus('thinking', 'מתחבר...');
  showScreen('call');

  try {
    const { token, url } = await fetchToken();

    room = new LivekitClient.Room({
      adaptiveStream: true,
      dynacast: true,
      audioCaptureDefaults: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    // Subscribe to agent audio
    room.on(LivekitClient.RoomEvent.TrackSubscribed, (track, _pub, participant) => {
      if (track.kind === 'audio' && participant.identity !== room.localParticipant.identity) {
        const audioEl = track.attach();
        audioEl.autoplay = true;
        document.body.appendChild(audioEl);
        agentSource = attachAnalyser(new MediaStream([track.mediaStreamTrack]));
      }
    });

    // Track agent speaking state via active speakers
    room.on(LivekitClient.RoomEvent.ActiveSpeakersChanged, (speakers) => {
      const agentSpeaking = speakers.some(s => s.identity !== room.localParticipant.identity);
      if (agentSpeaking) setStatus('speaking', 'מדבר...');
      else               setStatus('listening', 'מקשיב...');
    });

    room.on(LivekitClient.RoomEvent.Disconnected, () => endCall(false));

    await room.connect(url, token);
    await room.localParticipant.setMicrophoneEnabled(true);

    // Hook up local mic to visualizer
    const micTrack = Array.from(room.localParticipant.audioTrackPublications.values())[0]?.track;
    if (micTrack) {
      micSource = attachAnalyser(new MediaStream([micTrack.mediaStreamTrack]));
    }

    initVisualizer();
    setStatus('listening', 'מקשיב...');
    startTimer();

  } catch (err) {
    console.error('Call failed:', err);
    alert('לא הצלחתי להתחבר. נסה שוב.');
    endCall(true);
  } finally {
    callBtn.disabled = false;
  }
}

async function endCall(userInitiated = true) {
  if (room) {
    try { await room.disconnect(); } catch (_) {}
    room = null;
  }
  if (audioCtx) {
    try { await audioCtx.close(); } catch (_) {}
    audioCtx = null;
    analyser = null;
  }
  document.querySelectorAll('audio').forEach(el => el.remove());
  stopTimer();
  showScreen('idle');
}

// ---------- Wire up ----------
callBtn.addEventListener('click', startCall);
hangupBtn.addEventListener('click', () => endCall(true));

// Resume audio context on first user gesture (iOS quirk)
document.addEventListener('touchstart', () => {
  if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
}, { once: true });
