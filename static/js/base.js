// Base JavaScript for AI Interviewer System

class NotificationManager {
    constructor() {
        this.container = document.getElementById('notification-container');
    }

    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        
        const iconMap = {
            success: 'fas fa-check-circle',
            warning: 'fas fa-exclamation-triangle',
            error: 'fas fa-exclamation-circle',
            info: 'fas fa-info-circle'
        };

        notification.innerHTML = `
            <div class="notification-header">
                <div class="notification-title">
                    <i class="${iconMap[type] || iconMap.info}"></i>
                    <span>${this.getTitleForType(type)}</span>
                </div>
                <button class="notification-close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="notification-message">${message}</div>
        `;

        // Add close functionality
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.remove(notification);
        });

        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.remove(notification);
            }, duration);
        }

        this.container.appendChild(notification);
        
        // Trigger animation
        setTimeout(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateX(0)';
        }, 10);

        return notification;
    }

    remove(notification) {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }

    getTitleForType(type) {
        const titles = {
            success: 'Success',
            warning: 'Warning',
            error: 'Error',
            info: 'Information'
        };
        return titles[type] || titles.info;
    }
}

class ModalManager {
    constructor() {
        this.activeModal = null;
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close modal when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.close();
            }
        });

        // Close modal with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                this.close();
            }
        });
    }

    show(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
            this.activeModal = modal;
            document.body.style.overflow = 'hidden';
        }
    }

    close() {
        if (this.activeModal) {
            this.activeModal.classList.remove('show');
            this.activeModal = null;
            document.body.style.overflow = '';
        }
    }
}

class APIClient {
    constructor() {
        this.baseURL = '';
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;

        // Decide headers based on body type: don't set Content-Type for FormData
        const isFormData = options && options.body instanceof FormData;
        const defaultHeaders = isFormData ? {} : { 'Content-Type': 'application/json' };
        const config = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...(options && options.headers ? options.headers : {})
            }
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return await response.text();
            }
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async get(endpoint, params = {}) {
        const url = new URL(`${this.baseURL}${endpoint}`, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key] !== undefined && params[key] !== null) {
                url.searchParams.append(key, params[key]);
            }
        });

        return this.request(url.pathname + url.search, {
            method: 'GET'
        });
    }

    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }

    async uploadFile(endpoint, file, additionalData = {}) {
        const formData = new FormData();
        formData.append('file', file);
        
        Object.keys(additionalData).forEach(key => {
            formData.append(key, additionalData[key]);
        });

        return this.request(endpoint, {
            method: 'POST',
            body: formData
        });
    }
}

class SystemStatusChecker {
    constructor(apiClient, notificationManager) {
        this.apiClient = apiClient;
        this.notificationManager = notificationManager;
    }

    async checkStatus() {
        try {
            const status = await this.apiClient.get('/system-status');
            return status;
        } catch (error) {
            console.error('Failed to check system status:', error);
            throw error;
        }
    }

    renderStatus(status) {
        const speechStatus = status.speech_services;
        const visionStatus = status.vision_services;
        const llmProvider = status.llm_provider || 'Ollama';
        const ollamaModel = status.ollama_model || 'llama3.2';
        const ollamaUrl = status.ollama_url || 'http://localhost:11434';

        return `
            <div class="system-status">
                <div class="status-section">
                    <h4><i class="fas fa-microphone"></i> Speech Services</h4>
                    <div class="status-items">
                        <div class="status-item">
                            <span>Speech-to-Text (Whisper):</span>
                            <span class="status-badge ${speechStatus.whisper_available ? 'success' : 'error'}">
                                ${speechStatus.whisper_available ? 'Available' : 'Not Available'}
                            </span>
                        </div>
                        <div class="status-item">
                            <span>Text-to-Speech:</span>
                            <span class="status-badge ${speechStatus.tts_available ? 'success' : 'error'}">
                                ${speechStatus.tts_available ? 'Available' : 'Not Available'}
                            </span>
                        </div>
                    </div>
                </div>

                <div class="status-section">
                    <h4><i class="fas fa-video"></i> Computer Vision</h4>
                    <div class="status-items">
                        <div class="status-item">
                            <span>MediaPipe:</span>
                            <span class="status-badge ${visionStatus.mediapipe_available ? 'success' : 'error'}">
                                ${visionStatus.mediapipe_available ? 'Available' : 'Not Available'}
                            </span>
                        </div>
                        <div class="status-item">
                            <span>OpenCV Fallback:</span>
                            <span class="status-badge ${visionStatus.opencv_available ? 'success' : 'error'}">
                                ${visionStatus.opencv_available ? 'Available' : 'Not Available'}
                            </span>
                        </div>
                    </div>
                </div>

                <div class="status-section">
                    <h4><i class="fas fa-brain"></i> AI Services</h4>
                    <div class="status-items">
                        <div class="status-item">
                            <span>Provider:</span>
                            <span class="status-badge success">${llmProvider}</span>
                        </div>
                        <div class="status-item">
                            <span>Model:</span>
                            <span class="status-badge success">${ollamaModel}</span>
                        </div>
                        <div class="status-item">
                            <span>Endpoint:</span>
                            <span class="status-badge ${ollamaUrl ? 'success' : 'warning'}">${ollamaUrl}</span>
                        </div>
                    </div>
                </div>

                <div class="status-summary">
                    <div class="summary-item">
                        <strong>Overall Status:</strong>
                        <span class="status-badge ${this.getOverallStatus(status) === 'good' ? 'success' : 'warning'}">
                            ${this.getOverallStatusText(status)}
                        </span>
                    </div>
                </div>
            </div>

            <style>
                .system-status { font-size: 14px; }
                .status-section { margin-bottom: 20px; }
                .status-section h4 { 
                    color: var(--text-primary); 
                    margin-bottom: 10px; 
                    display: flex; 
                    align-items: center; 
                    gap: 8px; 
                }
                .status-items { margin-left: 20px; }
                .status-item { 
                    display: flex; 
                    justify-content: space-between; 
                    margin-bottom: 8px; 
                    padding: 4px 0;
                }
                .status-badge { 
                    padding: 2px 8px; 
                    border-radius: 4px; 
                    font-size: 12px; 
                    font-weight: 500; 
                }
                .status-badge.success { 
                    background-color: #dcfce7; 
                    color: #166534; 
                }
                .status-badge.warning { 
                    background-color: #fef3c7; 
                    color: #92400e; 
                }
                .status-badge.error { 
                    background-color: #fee2e2; 
                    color: #991b1b; 
                }
                .status-summary { 
                    border-top: 1px solid var(--border-color); 
                    padding-top: 15px; 
                }
                .summary-item { 
                    display: flex; 
                    justify-content: space-between; 
                    align-items: center; 
                }
            </style>
        `;
    }

    getOverallStatus(status) {
        const speechOk = status.speech_services.whisper_available && status.speech_services.tts_available;
        const visionOk = status.vision_services.mediapipe_available || status.vision_services.opencv_available;
        
        return speechOk && visionOk ? 'good' : 'partial';
    }

    getOverallStatusText(status) {
        const overall = this.getOverallStatus(status);
        return overall === 'good' ? 'Fully Functional' : 'Partially Functional';
    }
}

// Global instances
const notificationManager = new NotificationManager();
const modalManager = new ModalManager();
const apiClient = new APIClient();
const systemStatusChecker = new SystemStatusChecker(apiClient, notificationManager);

// Initialize base functionality
document.addEventListener('DOMContentLoaded', function() {
    // System status button
    const systemStatusBtn = document.getElementById('system-status-btn');
    const systemStatusModal = document.getElementById('system-status-modal');
    const closeStatusModal = document.getElementById('close-status-modal');
    const systemStatusContent = document.getElementById('system-status-content');

    if (systemStatusBtn) {
        systemStatusBtn.addEventListener('click', async function() {
            modalManager.show('system-status-modal');
            
            try {
                const status = await systemStatusChecker.checkStatus();
                systemStatusContent.innerHTML = systemStatusChecker.renderStatus(status);
            } catch (error) {
                systemStatusContent.innerHTML = `
                    <div class="error-message">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Failed to load system status: ${error.message}</p>
                    </div>
                `;
            }
        });
    }

    if (closeStatusModal) {
        closeStatusModal.addEventListener('click', function() {
            modalManager.close();
        });
    }

    // Global error handler
    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled promise rejection:', event.reason);
        notificationManager.show(
            'An unexpected error occurred. Please try again.',
            'error'
        );
    });

    // Global error handler for regular errors
    window.addEventListener('error', function(event) {
        console.error('Global error:', event.error);
        notificationManager.show(
            'An unexpected error occurred. Please refresh the page.',
            'error'
        );
    });
});

// Utility functions
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(date));
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Export global objects for use in other scripts
window.AIInterviewer = {
    notificationManager,
    modalManager,
    apiClient,
    systemStatusChecker,
    formatTime,
    formatDate,
    debounce,
    throttle
};

