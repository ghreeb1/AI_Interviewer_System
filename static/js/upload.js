// Upload Page JavaScript

class CVUploader {
    constructor() {
        this.currentSessionId = null;
        this.presetDuration = 15;
        this.uploadArea = document.getElementById('upload-area');
        this.fileInput = document.getElementById('cv-file-input');
        this.browseBtn = document.getElementById('browse-btn');
        this.uploadProgress = document.getElementById('upload-progress');
        this.progressFill = document.getElementById('progress-fill');
        this.progressText = document.getElementById('progress-text');
        this.uploadSuccess = document.getElementById('upload-success');
        this.cvSummary = document.getElementById('cv-summary');
        this.startInterviewBtn = document.getElementById('start-interview-btn');

        this.setupEventListeners();
        // Presets removed from UI; keep fixed default duration
        this.createSession();
    }

    setupEventListeners() {
        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                if (this._uploading) return; // prevent double upload
                this._uploading = true;
                this.handleFile(e.target.files[0]).finally(() => {
                    this._uploading = false;
                });
            }
        });

        // Browse button click
        this.browseBtn.addEventListener('click', () => {
            this.fileInput.click();
        });

        // Upload area click
        this.uploadArea.addEventListener('click', () => {
            if (this._uploading) return;
            this.fileInput.click();
        });

        // Drag and drop
        this.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadArea.classList.add('dragover');
        });

        this.uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
        });

        this.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                if (this._uploading) return;
                this._uploading = true;
                this.handleFile(files[0]).finally(() => {
                    this._uploading = false;
                });
            }
        });

        // Start interview button
        this.startInterviewBtn.addEventListener('click', () => {
            this.startInterview();
        });
    }

    async createSession() {
        try {
            // Read optional controls if present
            const defaultDuration = this.presetDuration || 15;
            const response = await window.AIInterviewer.apiClient.post('/api/session/create', {
                duration_minutes: defaultDuration,
                total_questions: 8
            });
            this.currentSessionId = response.session_id;
            console.log('Session created:', this.currentSessionId);
        } catch (error) {
            console.error('Failed to create session:', error);
            window.AIInterviewer.notificationManager.show(
                'Failed to create interview session. Please refresh the page.',
                'error'
            );
        }
    }

    validateFile(file) {
        const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain'
        ];

        const maxSize = 10 * 1024 * 1024; // 10MB

        if (!allowedTypes.includes(file.type)) {
            throw new Error('Please upload a PDF, DOCX, or TXT file.');
        }

        if (file.size > maxSize) {
            throw new Error('File size must be less than 10MB.');
        }

        return true;
    }

    async handleFile(file) {
        try {
            // Validate file
            this.validateFile(file);

            // Show progress
            this.showProgress();

            // Simulate progress for better UX
            this.animateProgress(0, 30, 500);

            // Upload file
            const response = await window.AIInterviewer.apiClient.uploadFile(
                `/api/session/${this.currentSessionId}/upload-cv`,
                file
            );

            // Complete progress
            this.animateProgress(30, 100, 1000);

            // Show success after progress completes
            setTimeout(() => {
                this.showSuccess(response, file.name);
            }, 1500);

        } catch (error) {
            console.error('File upload failed:', error);
            this.showError(error.message);
            this._uploading = false;
        }
    }

    showProgress() {
        this.uploadArea.style.display = 'none';
        this.uploadSuccess.style.display = 'none';
        this.uploadProgress.style.display = 'block';
        this.progressFill.style.width = '0%';
        this.progressText.textContent = 'Uploading and parsing CV...';
    }

    animateProgress(from, to, duration) {
        const start = Date.now();
        const animate = () => {
            const elapsed = Date.now() - start;
            const progress = Math.min(elapsed / duration, 1);
            const currentValue = from + (to - from) * progress;
            
            this.progressFill.style.width = `${currentValue}%`;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        animate();
    }

    showSuccess(response, filename) {
        this.uploadProgress.style.display = 'none';
        this.uploadSuccess.style.display = 'block';

        // Update CV summary
        this.cvSummary.innerHTML = `
            <div class="cv-summary-item">
                <i class="fas fa-file"></i>
                <span class="cv-summary-label">File:</span>
                <span class="cv-summary-value">${filename}</span>
            </div>
            <div class="cv-summary-item">
                <i class="fas fa-cogs"></i>
                <span class="cv-summary-label">Skills Found:</span>
                <span class="cv-summary-value">${response.skills_found}</span>
            </div>
            <div class="cv-summary-item">
                <i class="fas fa-graduation-cap"></i>
                <span class="cv-summary-label">Education:</span>
                <span class="cv-summary-value">${response.education_entries} entries</span>
            </div>
            <div class="cv-summary-item">
                <i class="fas fa-briefcase"></i>
                <span class="cv-summary-label">Experience:</span>
                <span class="cv-summary-value">${response.experience_entries} entries</span>
            </div>
        `;

        window.AIInterviewer.notificationManager.show(
            'CV uploaded and parsed successfully!',
            'success'
        );
    }

    showError(message) {
        this.uploadProgress.style.display = 'none';
        this.uploadArea.style.display = 'block';
        
        window.AIInterviewer.notificationManager.show(
            message,
            'error'
        );
    }

    async startInterview() {
        if (!this.currentSessionId) {
            window.AIInterviewer.notificationManager.show(
                'No active session. Please refresh the page.',
                'error'
            );
            return;
        }

        try {
            this.startInterviewBtn.disabled = true;
            this.startInterviewBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';

            await window.AIInterviewer.apiClient.post(`/api/session/${this.currentSessionId}/start`);
            
            // Redirect to interview page
            window.location.href = `/interview/${this.currentSessionId}`;

        } catch (error) {
            console.error('Failed to start interview:', error);
            window.AIInterviewer.notificationManager.show(
                'Failed to start interview: ' + error.message,
                'error'
            );
            
            this.startInterviewBtn.disabled = false;
            this.startInterviewBtn.innerHTML = '<i class="fas fa-play"></i> Start Interview';
        }
    }
}

// Initialize uploader when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new CVUploader();
});

