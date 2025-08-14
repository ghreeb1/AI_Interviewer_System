// Results Page JavaScript

class ResultsViewer {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.resultsData = null;
        this.chart = null;
        
        // DOM elements
        this.loadingResults = document.getElementById('loading-results');
        this.resultsContent = document.getElementById('results-content');
        this.errorState = document.getElementById('error-state');
        this.retryResultsBtn = document.getElementById('retry-results');
        
        // Summary elements
        this.interviewDuration = document.getElementById('interview-duration');
        this.cvMatchScore = document.getElementById('cv-match-score');
        this.eyeContactScore = document.getElementById('eye-contact-score');
        this.postureScore = document.getElementById('posture-score');
        this.responseCount = document.getElementById('response-count');
        
        // Analysis elements
        this.behaviorInsights = document.getElementById('behavior-insights');
        this.recommendationsList = document.getElementById('recommendations-list');
        this.transcript = document.getElementById('transcript');
        
        // Control elements
        this.toggleTranscriptBtn = document.getElementById('toggle-transcript');
        this.transcriptContent = document.getElementById('transcript-content');
        this.downloadReportBtn = document.getElementById('download-report');
        this.newInterviewBtn = document.getElementById('new-interview');
        this.deleteSessionBtn = document.getElementById('delete-session');
        
        this.initialize();
    }

    async initialize() {
        try {
            this.setupEventListeners();
            await this.loadResults();
        } catch (error) {
            console.error('Failed to initialize results viewer:', error);
            this.showError();
        }
    }

    setupEventListeners() {
        // Retry button
        if (this.retryResultsBtn) {
            this.retryResultsBtn.addEventListener('click', () => {
                this.loadResults();
            });
        }

        // Toggle transcript
        if (this.toggleTranscriptBtn) {
            this.toggleTranscriptBtn.addEventListener('click', () => {
                this.toggleTranscript();
            });
        }

        // Action buttons
        if (this.downloadReportBtn) {
            this.downloadReportBtn.addEventListener('click', () => {
                this.downloadReport();
            });
        }

        if (this.newInterviewBtn) {
            this.newInterviewBtn.addEventListener('click', () => {
                window.location.href = '/';
            });
        }

        if (this.deleteSessionBtn) {
            this.deleteSessionBtn.addEventListener('click', () => {
                this.deleteSession();
            });
        }
    }

    async loadResults() {
        try {
            this.showLoading();
            
            // Get session results
            const response = await window.AIInterviewer.apiClient.post(`/api/session/${this.sessionId}/end`);
            this.resultsData = response;
            
            this.renderResults();
            this.showResults();
            
        } catch (error) {
            console.error('Failed to load results:', error);
            this.showError();
        }
    }

    renderResults() {
        const { summary, transcript, duration_minutes } = this.resultsData;
        
        // Update duration
            this.interviewDuration.textContent = `${duration_minutes} minutes`;
        
        // Update summary scores
        this.cvMatchScore.textContent = `${summary.cv_match_score}%`;
        this.eyeContactScore.textContent = `${Math.round(summary.behavior_summary.average_eye_contact_score * 100)}%`;
        this.postureScore.textContent = `${Math.round((summary.behavior_summary.average_posture_score || 0) * 100)}%`;
        this.responseCount.textContent = Math.floor(summary.total_messages / 2); // Divide by 2 for exchanges
        
        // Render behavior insights
        this.renderBehaviorInsights(summary.behavior_summary);
        
        // Render recommendations
        this.renderRecommendations(summary.recommendations);
        
        // Render transcript
        this.renderTranscript(transcript);
        
        // Create behavior chart
        this.createBehaviorChart(summary.behavior_summary);
    }

    renderBehaviorInsights(behaviorSummary) {
        this.behaviorInsights.innerHTML = `
            <div class="insight-item">
                <div class="insight-value">${Math.round(behaviorSummary.average_attention_score * 100)}%</div>
                <div class="insight-label">Average Attention</div>
            </div>
            <div class="insight-item">
                <div class="insight-value">${Math.round(behaviorSummary.average_eye_contact_score * 100)}%</div>
                <div class="insight-label">Eye Contact</div>
            </div>
            <div class="insight-item">
                <div class="insight-value">${behaviorSummary.total_gestures}</div>
                <div class="insight-label">Hand Gestures</div>
            </div>
            <div class="insight-item">
                <div class="insight-value">${behaviorSummary.engagement_level}</div>
                <div class="insight-label">Engagement Level</div>
            </div>
        `;
    }

    renderRecommendations(recommendations) {
        this.recommendationsList.innerHTML = recommendations.map(recommendation => `
            <div class="recommendation-item">
                <div class="recommendation-icon">
                    <i class="fas fa-lightbulb"></i>
                </div>
                <div class="recommendation-text">${recommendation}</div>
            </div>
        `).join('');
    }

    renderTranscript(transcript) {
        this.transcript.innerHTML = transcript.map(message => {
            const time = window.AIInterviewer.formatDate(message.timestamp);
            const role = message.role === 'interviewer' ? 'interviewer' : 'candidate';
            const avatar = role === 'interviewer' ? 'fas fa-robot' : 'fas fa-user';
            const sender = role === 'interviewer' ? 'AI Interviewer' : 'You';
            
            return `
                <div class="transcript-message ${role}">
                    <div class="transcript-avatar">
                        <i class="${avatar}"></i>
                    </div>
                    <div class="transcript-content-text">
                        <div class="transcript-sender">${sender}</div>
                        <div class="transcript-text">${message.content}</div>
                        <div class="transcript-time">${time}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    createBehaviorChart(behaviorSummary) {
        const ctx = document.getElementById('behavior-chart');
        if (!ctx) return;

        // Destroy existing chart if it exists
        if (this.chart) {
            this.chart.destroy();
        }

        const data = {
            labels: ['Eye Contact', 'Posture', 'Attention', 'Engagement'],
            datasets: [{
                label: 'Performance Score',
                data: [
                    behaviorSummary.average_eye_contact_score * 100,
                    (behaviorSummary.average_posture_score || 0) * 100,
                    behaviorSummary.average_attention_score * 100,
                    behaviorSummary.engagement_level === 'High' ? 90 : 
                    behaviorSummary.engagement_level === 'Medium' ? 60 : 30
                ],
                backgroundColor: [
                    'rgba(37, 99, 235, 0.8)',
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(139, 92, 246, 0.8)'
                ],
                borderColor: [
                    'rgba(37, 99, 235, 1)',
                    'rgba(16, 185, 129, 1)',
                    'rgba(245, 158, 11, 1)',
                    'rgba(139, 92, 246, 1)'
                ],
                borderWidth: 2
            }]
        };

        const config = {
            type: 'radar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 20
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        };

        this.chart = new Chart(ctx, config);
    }

    toggleTranscript() {
        const isVisible = this.transcriptContent.style.display !== 'none';
        this.transcriptContent.style.display = isVisible ? 'none' : 'block';
        
        this.toggleTranscriptBtn.classList.toggle('expanded', !isVisible);
        this.toggleTranscriptBtn.innerHTML = isVisible 
            ? '<i class="fas fa-chevron-down"></i> <span>Show Transcript</span>'
            : '<i class="fas fa-chevron-up"></i> <span>Hide Transcript</span>';
    }

    downloadReport() {
        if (!this.resultsData) return;
        
        const reportData = {
            sessionId: this.sessionId,
            duration: this.resultsData.duration_minutes,
            summary: this.resultsData.summary,
            transcript: this.resultsData.transcript,
            generatedAt: new Date().toISOString()
        };
        
        const blob = new Blob([JSON.stringify(reportData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview-report-${this.sessionId}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        window.AIInterviewer.notificationManager.show(
            'Interview report downloaded successfully!',
            'success'
        );
    }

    async deleteSession() {
        const confirmed = confirm(
            'Are you sure you want to delete this interview session? This action cannot be undone.'
        );
        
        if (!confirmed) return;
        
        try {
            await window.AIInterviewer.apiClient.delete(`/api/session/${this.sessionId}`);
            
            window.AIInterviewer.notificationManager.show(
                'Interview session deleted successfully.',
                'success'
            );
            
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
            
        } catch (error) {
            console.error('Failed to delete session:', error);
            window.AIInterviewer.notificationManager.show(
                'Failed to delete session: ' + error.message,
                'error'
            );
        }
    }

    showLoading() {
        this.loadingResults.style.display = 'block';
        this.resultsContent.style.display = 'none';
        this.errorState.style.display = 'none';
    }

    showResults() {
        this.loadingResults.style.display = 'none';
        this.resultsContent.style.display = 'block';
        this.errorState.style.display = 'none';
    }

    showError() {
        this.loadingResults.style.display = 'none';
        this.resultsContent.style.display = 'none';
        this.errorState.style.display = 'block';
    }
}

// Initialize results viewer when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const sessionId = window.location.pathname.split('/').pop();
    new ResultsViewer(sessionId);
});

