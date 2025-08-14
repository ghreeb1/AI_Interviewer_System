(function(){
    const fileInput = document.getElementById('ats-file');
    const dropzone = document.getElementById('ats-dropzone');
    const startBtn = document.getElementById('start-ats');
    const nameInput = document.getElementById('candidate-name');
    const jdInput = document.getElementById('job-description');
    const resultEl = document.getElementById('ats-result');
    const progressEl = document.getElementById('ats-progress');
    const progressFill = document.getElementById('ats-progress-fill');
    const progressText = document.getElementById('ats-progress-text');

    let selectedFile = null;

    function updateStartEnabled(){
        startBtn.disabled = !(selectedFile && jdInput.value.trim().length > 0);
    }

    dropzone.addEventListener('click', ()=> fileInput.click());
    dropzone.addEventListener('dragover', (e)=>{ e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', (e)=>{ e.preventDefault(); dropzone.classList.remove('dragover'); });
    dropzone.addEventListener('drop', (e)=>{
        e.preventDefault(); dropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            selectedFile = e.dataTransfer.files[0];
            dropzone.querySelector('.dz-text strong').textContent = selectedFile.name;
            updateStartEnabled();
        }
    });

    fileInput.addEventListener('change', (e)=>{
        if (e.target.files[0]){
            selectedFile = e.target.files[0];
            dropzone.querySelector('.dz-text strong').textContent = selectedFile.name;
            updateStartEnabled();
        }
    });

    jdInput.addEventListener('input', updateStartEnabled);

    function animateProgress(from, to, duration){
        const start = Date.now();
        const animate = () => {
            const elapsed = Date.now() - start;
            const progress = Math.min(elapsed / duration, 1);
            const value = from + (to - from) * progress;
            progressFill.style.width = value + '%';
            if (progress < 1) requestAnimationFrame(animate);
        };
        animate();
    }

    startBtn.addEventListener('click', async ()=>{
        if (!selectedFile) return;
        try {
            startBtn.disabled = true;
            progressEl.style.display = 'block';
            progressFill.style.width = '0%';
            progressText.textContent = 'Uploading and analyzing...';
            animateProgress(0, 40, 600);

            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('job_description', jdInput.value.trim());
            if (nameInput.value.trim()) formData.append('candidate_name', nameInput.value.trim());

            const response = await window.AIInterviewer.apiClient.request('/api/ats/analyze', {
                method: 'POST',
                body: formData
            });

            animateProgress(40, 100, 800);
            setTimeout(()=>{
                progressEl.style.display = 'none';
                renderResult(response);
            }, 900);
        } catch (err){
            progressEl.style.display = 'none';
            window.AIInterviewer.notificationManager.show(err.message || 'Failed to analyze CV', 'error');
            startBtn.disabled = false;
        }
    });

    function renderResult(data){
        resultEl.style.display = 'block';
        const matched = (data.matched_skills||[]).map(s=>`<span class="chip good">${s}</span>`).join(' ');
        const missing = (data.missing_skills||[]).map(s=>`<span class="chip missing">${s}</span>`).join(' ');
        const recs = (data.recommendations||[]).map(r=>`<li><i class="fas fa-lightbulb"></i> ${r}</li>`).join('');
        resultEl.innerHTML = `
            <h4>ATS Results ${data.candidate_name ? 'for ' + data.candidate_name : ''}</h4>
            <div class="score">${data.compatibility_score}% Match</div>
            <div class="section">
                <div class="section-header"><div class="section-title">Matched Skills</div></div>
                <div class="section-body"><div class="skills">${matched || 'No direct matches detected'}</div></div>
            </div>
            <div class="section" style="margin-top:12px;">
                <div class="section-header"><div class="section-title">Missing Skills</div></div>
                <div class="section-body"><div class="skills">${missing || 'All key skills appear covered'}</div></div>
            </div>
            <div class="section" style="margin-top:12px;">
                <div class="section-header"><div class="section-title">Recommendations</div></div>
                <div class="section-body"><ul class="bullets">${recs || '<li>Looks good. Tailor your CV to highlight relevant projects.</li>'}</ul></div>
            </div>
        `;
        window.scrollTo({ top: resultEl.offsetTop - 80, behavior: 'smooth' });
    }
})();


