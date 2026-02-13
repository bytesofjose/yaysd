document.getElementById('downloadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const urlInput = document.getElementById('urlInput');
    const downloadBtn = document.getElementById('downloadBtn');
    const feedbackContainer = document.getElementById('feedbackContainer');
    const feedbackText = document.getElementById('feedbackText');
    const loader = feedbackContainer.querySelector('.loader');
    
    const url = urlInput.value.trim();
    if (!url) return;

    // Reset UI
    feedbackContainer.classList.remove('hidden', 'success', 'error');
    loader.classList.remove('hidden');
    feedbackText.textContent = 'Procesando descarga... Por favor espera.';
    downloadBtn.disabled = true;
    downloadBtn.style.opacity = '0.5';

    try {
        const formData = new FormData();
        formData.append('url', url);

        const response = await fetch('/download', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        loader.classList.add('hidden');
        feedbackText.textContent = data.message;
        
        if (data.status === 'success') {
            feedbackContainer.classList.add('success');
            urlInput.value = ''; // Clean input on success
        } else {
            feedbackContainer.classList.add('error');
        }

    } catch (error) {
        loader.classList.add('hidden');
        feedbackContainer.classList.add('error');
        feedbackText.textContent = 'Error de conexión con el servidor.';
    } finally {
        downloadBtn.disabled = false;
        downloadBtn.style.opacity = '1';
    }
});
