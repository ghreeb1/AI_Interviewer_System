// Interview Page JavaScript

class InterviewSession {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.websocket = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.isPaused = false;
        this.timeRemaining = 900; // 15 minutes in seconds
        this.timerInterval = null;
        this.questions = [];
        this.totalQuestions = 0;
        this.questionsAsked = 0;
        
        // DOM elements
        this.timer = document.getElementById('timer');
        this.webcamVideo = document.getElementById('webcam-video');
        this.chatMessages = document.getElementById('chat-messages');
        this.voiceBtn = document.getElementById('voice-btn');
        this.voiceStatus = document.getElementById('voice-status');
        this.textInput = document.getElementById('text-input');
        this.sendTextBtn = document.getElementById('send-text-btn');
        this.textInputSection = document.getElementById('text-input-section');
        this.toggleTextInputBtn = document.getElementById('toggle-text-input');
        this.toggleCameraBtn = document.getElementById('toggle-camera');
        this.toggleMicBtn = document.getElementById('toggle-mic');
        this.pauseInterviewBtn = document.getElementById('pause-interview');
        this.durationButtons = document.querySelectorAll('[data-duration]');
        this.questionButtons = document.querySelectorAll('[data-questions]');
        this.endInterviewBtn = document.getElementById('end-interview');
        this.loadingModal = document.getElementById('loading-modal');
        this.loadingText = document.getElementById('loading-text');
        this.endInterviewModal = document.getElementById('end-interview-modal');
        this.cancelEndBtn = document.getElementById('cancel-end');
        this.confirmEndBtn = document.getElementById('confirm-end');
        
        // Behavior metrics elements
        this.eyeContactScore = document.getElementById('eye-contact-score');
        this.postureScore = document.getElementById('posture-score');
        this.gestureCount = document.getElementById('gesture-count');

        // New progress bar elements (axes box)
        this.engagementBar = document.getElementById('engagement-bar');
        this.confidenceBar = document.getElementById('confidence-bar');
        this.stressBar = document.getElementById('stress-bar');
        this.engagementPercent = document.getElementById('engagement-percent');
        this.confidencePercent = document.getElementById('confidence-percent');
        this.stressPercent = document.getElementById('stress-percent');
        
        this.initialize();
    }

    async initialize() {
        try {
            this.showLoading('Initializing interview session...');
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Initialize webcam
            await this.initializeWebcam();
            
            // Connect WebSocket
            await this.connectWebSocket();
            
            // Load config (duration, planned questions)
            await this.loadSessionConfig();
            // Start timer
            this.startTimer();
            
            // Don't block UI waiting for initial question; show placeholder now
            const initialMessageEl = document.getElementById('initial-message');
            if (initialMessageEl) {
                initialMessageEl.textContent = 'Preparing your introduction...';
            }
            // Fire and forget to fetch session and update initial message if available
            this.getInitialQuestion();
            this.renderPlannedQuestions();
            
            this.hideLoading();
            
        } catch (error) {
            console.error('Failed to initialize interview:', error);
            this.showError('Failed to initialize interview session');
        }
    }

    async loadSessionConfig() {
        try {
            const data = await window.AIInterviewer.apiClient.get(`/api/session/${this.sessionId}`);
            if (data) {
                if (typeof data.max_duration_seconds === 'number' && data.max_duration_seconds > 0) {
                    this.timeRemaining = data.max_duration_seconds;
                }
                this.questions = Array.isArray(data.questions) ? data.questions : [];
                this.totalQuestions = typeof data.total_questions === 'number' ? data.total_questions : (this.questions.length || 0);
                this.questionsAsked = typeof data.questions_asked === 'number' ? data.questions_asked : 0;
            }
        } catch (e) {
            console.warn('Failed to load session config; using defaults');
        }
    }

    setupEventListeners() {
        // Voice button
        this.voiceBtn.addEventListener('mousedown', () => this.startRecording());
        this.voiceBtn.addEventListener('mouseup', () => this.stopRecording());
        this.voiceBtn.addEventListener('mouseleave', () => this.stopRecording());
        
        // Touch events for mobile
        this.voiceBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.startRecording();
        });
        this.voiceBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.stopRecording();
        });

        // Text input
        this.sendTextBtn.addEventListener('click', () => this.sendTextMessage());
        this.textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendTextMessage();
            }
        });

        // Toggle text input
        this.toggleTextInputBtn.addEventListener('click', () => this.toggleTextInput());

        // Camera and mic controls (optional elements)
        if (this.toggleCameraBtn) {
            this.toggleCameraBtn.addEventListener('click', () => this.toggleCamera());
        }
        if (this.toggleMicBtn) {
            this.toggleMicBtn.addEventListener('click', () => this.toggleMicrophone());
        }

        // Interview controls
        this.pauseInterviewBtn.addEventListener('click', () => this.pauseInterview());
        this.endInterviewBtn.addEventListener('click', () => this.showEndInterviewModal());

        // Preset controls (non-blocking; only apply before start ideally)
        this.durationButtons.forEach(btn => {
            btn.addEventListener('click', async () => {
                const minutes = parseInt(btn.getAttribute('data-duration'));
                if (![10,15,30].includes(minutes)) return;
                try {
                    // Update server by recreating session settings is out of scope here; display hint
                    window.AIInterviewer.notificationManager.show('Duration presets can be set on the upload page before starting.', 'info', 3000);
                } catch (e) {}
            });
        });
        this.questionButtons.forEach(btn => {
            btn.addEventListener('click', async () => {
                const count = parseInt(btn.getAttribute('data-questions'));
                if (!count) return;
                window.AIInterviewer.notificationManager.show('Question count preset is set at session creation time.', 'info', 3000);
            });
        });

        // End interview modal
        this.cancelEndBtn.addEventListener('click', () => this.hideEndInterviewModal());
        this.confirmEndBtn.addEventListener('click', () => this.endInterview());

        // Prevent accidental page refresh
        window.addEventListener('beforeunload', (e) => {
            if (!this.isPaused) {
                e.preventDefault();
                e.returnValue = 'Are you sure you want to leave? Your interview session will be lost.';
            }
        });
    }

    async initializeWebcam() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 1280, height: 720 },
                audio: true
            });
            
            this.webcamVideo.srcObject = stream;
            this.stream = stream;
            
            // Start video analysis
            this.startVideoAnalysis();
            
        } catch (error) {
            console.error('Failed to access webcam:', error);
            window.AIInterviewer.notificationManager.show(
                'Failed to access camera and microphone. Some features may not work.',
                'warning'
            );
        }
    }

    async connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
        };
        
        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus(false);
        };
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'transcription':
                this.addMessage('candidate', message.text);
                break;
            case 'ai_response':
                this.addMessage('interviewer', message.text);
                if (message.audio) {
                    this.playAudioResponse(message.audio);
                }
                try { this.questionsAsked += 1; } catch (e) { this.questionsAsked = 1; }
                this.renderPlannedQuestions();
                break;
            case 'vision_metrics':
                this.updateBehaviorMetrics(message.metrics);
                break;
            case 'error':
                window.AIInterviewer.notificationManager.show(message.message, 'error');
                break;
            case 'pong':
                // Keep-alive response
                break;
        }
    }

    startVideoAnalysis() {
        if (!this.stream) return;
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        const analyzeFrame = () => {
            if (this.isPaused) return;
            
            canvas.width = this.webcamVideo.videoWidth;
            canvas.height = this.webcamVideo.videoHeight;
            
            ctx.drawImage(this.webcamVideo, 0, 0);
            
            // Convert canvas to blob and send via WebSocket
            canvas.toBlob((blob) => {
                if (blob && this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    const reader = new FileReader();
                    reader.onload = () => {
                        const base64Data = reader.result.split(',')[1];
                        this.websocket.send(JSON.stringify({
                            type: 'video',
                            data: base64Data
                        }));
                    };
                    reader.readAsDataURL(blob);
                }
            }, 'image/jpeg', 0.8);
            
            // Analyze every 2 seconds
            setTimeout(analyzeFrame, 2000);
        };
        
        // Start analysis after video is ready
        this.webcamVideo.addEventListener('loadeddata', () => {
            setTimeout(analyzeFrame, 1000);
        });
    }

    async getInitialQuestion() {
        const initialMessageEl = document.getElementById('initial-message');
        const maxAttempts = 30; // ~30s
        const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                const data = await window.AIInterviewer.apiClient.get(`/api/session/${this.sessionId}`);
                if (data && data.initial_question) {
                    if (initialMessageEl) {
                        initialMessageEl.textContent = data.initial_question;
                    } else {
                        this.addMessage('interviewer', data.initial_question);
                    }
                    return;
                }
            } catch (error) {
                console.error('Failed to get session data:', error);
            }
            if (initialMessageEl && (attempt % 5 === 0)) {
                initialMessageEl.textContent = 'Still preparing your first question...';
            }
            await delay(1000);
        }
        // Give up politely; user can start by sending a message
        if (initialMessageEl) {
            initialMessageEl.textContent = 'You can start by introducing yourself while the system prepares.';
        }
    }

    startTimer() {
        this.updateTimerDisplay();
        
        this.timerInterval = setInterval(() => {
            this.timeRemaining--;
            this.updateTimerDisplay();
            
            if (this.timeRemaining <= 300) { // 5 minutes warning
                this.timer.classList.add('warning');
            }
            
            if (this.timeRemaining <= 60) { // 1 minute danger
                this.timer.classList.add('danger');
            }
            
            if (this.timeRemaining <= 0) {
                this.endInterview();
            }
        }, 1000);
    }

    updateTimerDisplay() {
        this.timer.textContent = window.AIInterviewer.formatTime(this.timeRemaining);
    }

    renderPlannedQuestions() {
        const listEl = document.getElementById('planned-questions');
        const remEl = document.getElementById('questions-remaining');
        if (listEl) {
            listEl.innerHTML = '';
            (this.questions || []).forEach((q) => {
                const li = document.createElement('li');
                li.textContent = q;
                listEl.appendChild(li);
            });
        }
        if (remEl) {
            const total = this.totalQuestions || (this.questions ? this.questions.length : 0);
            const remaining = Math.max(0, total - this.questionsAsked);
            remEl.textContent = `${remaining} of ${total} questions remaining`;
        }
    }

    async startRecording() {
        if (this.isRecording || !this.stream) return;
        
        try {
            this.isRecording = true;
            this.voiceBtn.classList.add('recording');
            this.voiceBtn.innerHTML = '<i class="fas fa-stop"></i> <span>Release to Send</span>';
            this.voiceStatus.textContent = 'Recording...';
            
            this.audioChunks = [];
            const audioTrack = this.stream.getAudioTracks()[0];
            if (!audioTrack || audioTrack.muted === true || audioTrack.enabled === false) {
                this.voiceStatus.textContent = 'Microphone is muted/disabled';
            }

            const options = { mimeType: 'audio/webm' };
            if (!MediaRecorder.isTypeSupported('audio/webm')) {
                options.mimeType = 'audio/webm;codecs=opus';
            }
            this.mediaRecorder = new MediaRecorder(this.stream, options);
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = () => { this.processRecording(); };
            
            this.mediaRecorder.start();
            
        } catch (error) {
            console.error('Failed to start recording:', error);
            this.isRecording = false;
            this.voiceBtn.classList.remove('recording');
            this.voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> <span>Hold to Speak</span>';
            this.voiceStatus.textContent = 'Recording failed';
        }
    }

    stopRecording() {
        if (!this.isRecording || !this.mediaRecorder) return;
        
        this.isRecording = false;
        this.voiceBtn.classList.remove('recording');
        this.voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> <span>Hold to Speak</span>';
            this.voiceStatus.textContent = 'Processing...';
        
        this.mediaRecorder.stop();
    }

    async processRecording() {
        if (this.audioChunks.length === 0) {
            this.voiceStatus.textContent = 'Ready to listen';
            return;
        }
        
        try {
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            const reader = new FileReader();
            
            reader.onload = () => {
                const base64Data = reader.result.split(',')[1];
                
                if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    this.websocket.send(JSON.stringify({
                        type: 'audio',
                        data: base64Data
                    }));
                }
            };
            
            reader.readAsDataURL(audioBlob);
            
        } catch (error) {
            console.error('Failed to process recording:', error);
            this.voiceStatus.textContent = 'Processing failed';
        }
    }

    sendTextMessage() {
        const message = this.textInput.value.trim();
        if (!message) return;
        
        this.addMessage('candidate', message);
        this.textInput.value = '';
        
        // Send to API
        window.AIInterviewer.apiClient.post(`/api/session/${this.sessionId}/message`, {
            role: 'candidate',
            content: message
        }).then(response => {
            if (response.ai_response) {
                this.addMessage('interviewer', response.ai_response);
            }
        }).catch(error => {
            console.error('Failed to send message:', error);
            window.AIInterviewer.notificationManager.show('Failed to send message', 'error');
        });
    }

    addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        
        const avatar = role === 'interviewer' ? 'fas fa-robot' : 'fas fa-user';
        const sender = role === 'interviewer' ? 'AI Interviewer' : 'You';
        const time = new Date().toLocaleTimeString();
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="${avatar}"></i>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">${sender}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-text">${content}</div>
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    playAudioResponse(base64Audio) {
        try {
            const audioData = atob(base64Audio);
            const audioArray = new Uint8Array(audioData.length);
            for (let i = 0; i < audioData.length; i++) {
                audioArray[i] = audioData.charCodeAt(i);
            }
            
            const audioBlob = new Blob([audioArray], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            
            audio.play().catch(error => {
                console.error('Failed to play audio response:', error);
            });
            
        } catch (error) {
            console.error('Failed to process audio response:', error);
        }
    }

    updateBehaviorMetrics(metrics) {
        if (this.eyeContactScore) {
            this.eyeContactScore.textContent = `${Math.round(metrics.eye_contact_score * 100)}%`;
        }
        if (this.postureScore) {
            this.postureScore.textContent = `${Math.round(metrics.posture_score * 100)}%`;
        }
        if (this.gestureCount) {
            this.gestureCount.textContent = metrics.gesture_count;
        }

        // Compute high-level metrics for the axes box
        const eye = typeof metrics.eye_contact_score === 'number' ? metrics.eye_contact_score : 0;
        const posture = typeof metrics.posture_score === 'number' ? metrics.posture_score : 0;
        const attention = typeof metrics.attention_score === 'number' ? metrics.attention_score : ((eye + posture) / 2);

        const engagement = Math.max(0, Math.min(1, attention));
        const confidence = Math.max(0, Math.min(1, (eye * 0.6 + posture * 0.4)));
        const stress = Math.max(0, Math.min(1, 1 - confidence * 0.8));

        if (this.engagementBar) {
            this.engagementBar.style.width = `${Math.round(engagement * 100)}%`;
        }
        if (this.confidenceBar) {
            this.confidenceBar.style.width = `${Math.round(confidence * 100)}%`;
        }
        if (this.stressBar) {
            this.stressBar.style.width = `${Math.round(stress * 100)}%`;
        }
        if (this.engagementPercent) {
            this.engagementPercent.textContent = `${Math.round(engagement * 100)}%`;
        }
        if (this.confidencePercent) {
            this.confidencePercent.textContent = `${Math.round(confidence * 100)}%`;
        }
        if (this.stressPercent) {
            this.stressPercent.textContent = `${Math.round(stress * 100)}%`;
        }
    }

    toggleTextInput() {
        const isVisible = this.textInputSection.style.display !== 'none';
        this.textInputSection.style.display = isVisible ? 'none' : 'block';
        this.toggleTextInputBtn.innerHTML = isVisible 
            ? '<i class="fas fa-keyboard"></i> <span>Use Text Input</span>'
            : '<i class="fas fa-microphone"></i> <span>Use Voice Input</span>';
    }

    toggleCamera() {
        if (!this.stream) return;
        
        const videoTrack = this.stream.getVideoTracks()[0];
        if (videoTrack) {
            videoTrack.enabled = !videoTrack.enabled;
            this.toggleCameraBtn.classList.toggle('active', videoTrack.enabled);
            this.toggleCameraBtn.classList.toggle('inactive', !videoTrack.enabled);
            this.toggleCameraBtn.innerHTML = videoTrack.enabled
                ? '<i class="fas fa-video"></i> <span>Camera On</span>'
                : '<i class="fas fa-video-slash"></i> <span>Camera Off</span>';
        }
    }

    toggleMicrophone() {
        if (!this.stream) return;
        
        const audioTrack = this.stream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.enabled = !audioTrack.enabled;
            if (this.toggleMicBtn) {
                this.toggleMicBtn.classList.toggle('active', audioTrack.enabled);
                this.toggleMicBtn.classList.toggle('inactive', !audioTrack.enabled);
                this.toggleMicBtn.innerHTML = audioTrack.enabled
                    ? '<i class="fas fa-microphone"></i> <span>Mic On</span>'
                    : '<i class="fas fa-microphone-slash"></i> <span>Mic Off</span>';
            }
            const statusEl = document.getElementById('audio-status');
            if (statusEl) {
                statusEl.textContent = audioTrack.enabled ? 'On' : 'Off';
            }
        }
    }

    pauseInterview() {
        this.isPaused = !this.isPaused;
        
        if (this.isPaused) {
            clearInterval(this.timerInterval);
            this.pauseInterviewBtn.innerHTML = '<i class="fas fa-play"></i> <span>Resume</span>';
            this.pauseInterviewBtn.classList.add('btn-success');
            this.pauseInterviewBtn.classList.remove('btn-warning');
        } else {
            this.startTimer();
            this.pauseInterviewBtn.innerHTML = '<i class="fas fa-pause"></i> <span>Pause</span>';
            this.pauseInterviewBtn.classList.add('btn-warning');
            this.pauseInterviewBtn.classList.remove('btn-success');
        }
    }

    showEndInterviewModal() {
        window.AIInterviewer.modalManager.show('end-interview-modal');
    }

    hideEndInterviewModal() {
        window.AIInterviewer.modalManager.close();
    }

    async endInterview() {
        try {
            this.hideEndInterviewModal();
            this.showLoading('Ending interview and generating results...');
            
            // Stop timer
            if (this.timerInterval) {
                clearInterval(this.timerInterval);
            }
            
            // Close WebSocket
            if (this.websocket) {
                this.websocket.close();
            }
            
            // Stop media streams
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
            
            // End session via API
            await window.AIInterviewer.apiClient.post(`/api/session/${this.sessionId}/end`);
            
            // Redirect to results
            window.location.href = `/results/${this.sessionId}`;
            
        } catch (error) {
            console.error('Failed to end interview:', error);
            this.hideLoading();
            window.AIInterviewer.notificationManager.show(
                'Failed to end interview properly. Redirecting to results...',
                'warning'
            );
            
            setTimeout(() => {
                window.location.href = `/results/${this.sessionId}`;
            }, 2000);
        }
    }

    updateConnectionStatus(connected) {
        const chatStatus = document.getElementById('chat-status');
        if (connected) {
            chatStatus.innerHTML = '<i class="fas fa-circle"></i> <span>Connected</span>';
            chatStatus.style.color = 'var(--success-color)';
        } else {
            chatStatus.innerHTML = '<i class="fas fa-circle"></i> <span>Disconnected</span>';
            chatStatus.style.color = 'var(--danger-color)';
        }
    }

    showLoading(message) {
        this.loadingText.textContent = message;
        window.AIInterviewer.modalManager.show('loading-modal');
    }

    hideLoading() {
        window.AIInterviewer.modalManager.close();
    }

    showError(message) {
        this.hideLoading();
        window.AIInterviewer.notificationManager.show(message, 'error');
    }
}

// Initialize interview session when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const sessionId = window.location.pathname.split('/').pop();
    new InterviewSession(sessionId);
});

