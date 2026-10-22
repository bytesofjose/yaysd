const form = document.getElementById('downloadForm');
const urlInput = document.getElementById('urlInput');
const downloadBtn = document.getElementById('downloadBtn');
const feedbackContainer = document.getElementById('feedbackContainer');
const feedbackText = document.getElementById('feedbackText');

const overlay = document.getElementById('orbOverlay');
const orbProgress = document.getElementById('orbProgress');
const orbPercent = document.getElementById('orbPercent');
const orbCount = document.getElementById('orbCount');
const orbBarFill = document.getElementById('orbBarFill');
const orbTitle = document.getElementById('orbTitle');
const orbStage = document.getElementById('orbStage');
const orbCancel = document.getElementById('orbCancel');

const RING_C = 2 * Math.PI * 52;
orbProgress.style.strokeDasharray = String(RING_C);
orbProgress.style.strokeDashoffset = String(RING_C);

let pollTimer = null;
let activeJob = null;

function showOverlay() {
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('locked');
}

function hideOverlay() {
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('locked');
}

function renderJob(job) {
    const pct = Math.max(0, Math.min(100, Number(job.percent) || 0));
    orbProgress.style.strokeDashoffset = String(RING_C * (1 - pct / 100));
    orbPercent.textContent = `${Math.round(pct)}%`;
    orbBarFill.style.width = `${pct}%`;
    if (job.total > 0) {
        orbCount.textContent = `${job.done}/${job.total} rolas`;
    } else {
        orbCount.textContent = 'Leyendo links…';
    }
    orbTitle.textContent = job.current_title || job.message || 'Trabajando…';
    const stageMap = {
        descargando: '⬇ Descargando audio',
        'convirtiendo a mp3': '⚙ Convirtiendo a MP3…',
        resolviendo: '🔍 Resolviendo URL…',
        listo: '✅ Listo'
    };
    orbStage.textContent = stageMap[job.stage] || job.stage || '';
}

function showFeedback(ok, msg) {
    feedbackContainer.classList.remove('hidden', 'success', 'error');
    feedbackContainer.classList.add(ok ? 'success' : 'error');
    feedbackText.textContent = msg;
}

async function pollJob(jobId) {
    try {
        const res = await fetch(`/api/job/${jobId}`);
        if (!res.ok) throw new Error('job perdido');
        const job = await res.json();
        renderJob(job);
        if (job.status === 'done' || job.status === 'error' || job.status === 'cancelled') {
            clearInterval(pollTimer);
            pollTimer = null;
            activeJob = null;
            hideOverlay();
            downloadBtn.disabled = false;
            const ok = job.status === 'done';
            showFeedback(ok, job.message || job.status);
            if (ok) urlInput.value = '';
        }
    } catch (err) {
        clearInterval(pollTimer);
        pollTimer = null;
        activeJob = null;
        hideOverlay();
        downloadBtn.disabled = false;
        showFeedback(false, 'Se perdió la conexión con el servidor.');
    }
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url || activeJob) return;

    feedbackContainer.classList.add('hidden');
    downloadBtn.disabled = true;
    showOverlay();
    renderJob({ percent: 0, total: 0, done: 0, current_title: '', stage: 'resolviendo', message: 'Resolviendo URL…' });

    try {
        const formData = new FormData();
        formData.append('url', url);
        const res = await fetch('/download', { method: 'POST', body: formData });
        const data = await res.json();
        if (!data.job_id) throw new Error(data.message || 'sin job');
        activeJob = data.job_id;
        pollTimer = setInterval(() => pollJob(activeJob), 1000);
        pollJob(activeJob);
    } catch (err) {
        hideOverlay();
        downloadBtn.disabled = false;
        showFeedback(false, 'Error de conexión con el servidor.');
    }
});

orbCancel.addEventListener('click', async () => {
    if (!activeJob) return;
    orbCancel.disabled = true;
    try {
        await fetch(`/api/job/${activeJob}/cancel`, { method: 'POST' });
    } catch (err) {
        /* poll loop will surface the state */
    }
    orbCancel.disabled = false;
});
