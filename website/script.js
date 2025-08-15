// Global variables
let latestVersion = '1.0.3';
let downloadCount = 1234;

// DOM Content Loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeWebsite();
    setupEventListeners();
    fetchLatestRelease();
    animateCounters();
});

// Initialize website
function initializeWebsite() {
    // Update version displays
    updateVersionDisplays();
    
    // Setup smooth scrolling for navigation links
    setupSmoothScrolling();
    
    // Setup mobile navigation
    setupMobileNavigation();
    
    // Setup pricing toggle
    setupPricingToggle();
    
    // Add scroll effects
    setupScrollEffects();
}

// Setup event listeners
function setupEventListeners() {
    // Navigation toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
        });
    }
    
    // Close mobile menu when clicking on a link
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navMenu?.classList.remove('active');
        });
    });
    
    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        const modal = document.getElementById('demoModal');
        if (event.target === modal) {
            closeDemo();
        }
    });
    
    // Handle escape key for modal
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeDemo();
        }
    });
}

// Update version displays
function updateVersionDisplays() {
    const elements = [
        'currentVersion',
        'downloadVersion'
    ];
    
    elements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = latestVersion;
        }
    });
    
    // Update last update date
    const lastUpdateElement = document.getElementById('lastUpdate');
    if (lastUpdateElement) {
        const today = new Date();
        const options = { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        };
        lastUpdateElement.textContent = today.toLocaleDateString('he-IL', options);
    }
}

// Fetch latest release from GitHub
async function fetchLatestRelease() {
    try {
        const response = await fetch('https://api.github.com/repos/danielpiro/idf-reader/releases/latest');
        const release = await response.json();
        
        if (release.tag_name) {
            latestVersion = release.tag_name.replace('v', '');
            updateVersionDisplays();
            
            // Update download button with real download URL
            const downloadButton = document.getElementById('downloadButton');
            if (downloadButton && release.assets && release.assets.length > 0) {
                const asset = release.assets.find(asset => 
                    asset.name.includes('.exe') || asset.name.includes('windows')
                ) || release.assets[0];
                
                downloadButton.href = asset.browser_download_url;
                downloadButton.onclick = null; // Remove the default onclick
            }
            
            // Update download count from GitHub API
            if (release.assets && release.assets[0]) {
                downloadCount = release.assets[0].download_count || downloadCount;
                updateDownloadCount();
            }
        }
    } catch (error) {
        console.log('Could not fetch latest release:', error);
        // Fallback to default download
        setupFallbackDownload();
    }
}

// Setup fallback download
function setupFallbackDownload() {
    const downloadButton = document.getElementById('downloadButton');
    if (downloadButton) {
        downloadButton.href = 'https://github.com/danielpiro/idf-reader/releases/latest';
        downloadButton.onclick = null;
    }
}

// Update download count display
function updateDownloadCount() {
    const downloadCountElement = document.getElementById('downloadCount');
    const totalDownloadsElement = document.getElementById('totalDownloads');
    
    if (downloadCountElement) {
        downloadCountElement.textContent = formatNumber(downloadCount) + '+';
    }
    
    if (totalDownloadsElement) {
        totalDownloadsElement.textContent = formatNumber(downloadCount);
    }
}

// Format number with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Download latest version
function downloadLatest() {
    // Track download
    if (typeof gtag !== 'undefined') {
        gtag('event', 'download', {
            event_category: 'software',
            event_label: `v${latestVersion}`
        });
    }
    
    // Increment download count for demo
    downloadCount++;
    updateDownloadCount();
    
    // Show thank you message
    showNotification('תודה על ההורדה! הקובץ יתחיל להיות מורד בקרוב.', 'success');
}

// Setup smooth scrolling
function setupSmoothScrolling() {
    const links = document.querySelectorAll('a[href^="#"]');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                const navbarHeight = document.querySelector('.navbar').offsetHeight;
                const targetPosition = targetElement.offsetTop - navbarHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// Setup mobile navigation
function setupMobileNavigation() {
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navToggle.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
    }
}

// Setup pricing toggle
function setupPricingToggle() {
    const pricingToggle = document.getElementById('pricingToggle');
    
    if (pricingToggle) {
        pricingToggle.addEventListener('change', function() {
            const monthlyElements = document.querySelectorAll('.monthly-price, .monthly-period');
            const yearlyElements = document.querySelectorAll('.yearly-price, .yearly-period');
            
            if (this.checked) {
                // Show yearly pricing
                monthlyElements.forEach(el => el.style.display = 'none');
                yearlyElements.forEach(el => el.style.display = 'inline');
            } else {
                // Show monthly pricing
                monthlyElements.forEach(el => el.style.display = 'inline');
                yearlyElements.forEach(el => el.style.display = 'none');
            }
        });
    }
}

// Setup scroll effects
function setupScrollEffects() {
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            navbar.style.background = 'rgba(255, 255, 255, 0.98)';
            navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
        } else {
            navbar.style.background = 'rgba(255, 255, 255, 0.95)';
            navbar.style.boxShadow = 'none';
        }
    });
    
    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Observe elements for animation
    const animatedElements = document.querySelectorAll('.feature-card, .pricing-card');
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// Animate counters
function animateCounters() {
    const counters = document.querySelectorAll('.stat-number');
    
    const animateCounter = (counter) => {
        const target = parseInt(counter.textContent.replace(/[^\d]/g, ''));
        const duration = 2000; // 2 seconds
        const start = performance.now();
        
        const updateCounter = (currentTime) => {
            const elapsed = currentTime - start;
            const progress = Math.min(elapsed / duration, 1);
            
            const current = Math.floor(progress * target);
            const originalText = counter.textContent;
            const suffix = originalText.replace(/[\d,]/g, '');
            
            counter.textContent = formatNumber(current) + suffix;
            
            if (progress < 1) {
                requestAnimationFrame(updateCounter);
            }
        };
        
        requestAnimationFrame(updateCounter);
    };
    
    // Intersection Observer for counters
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                counterObserver.unobserve(entry.target); // Only animate once
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => {
        counterObserver.observe(counter);
    });
}

// Demo modal functions
function openDemo() {
    const modal = document.getElementById('demoModal');
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
    
    // Track demo view
    if (typeof gtag !== 'undefined') {
        gtag('event', 'demo_view', {
            event_category: 'engagement'
        });
    }
}

function closeDemo() {
    const modal = document.getElementById('demoModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// Open changelog
function openChangelog() {
    window.open('https://github.com/danielpiro/idf-reader/releases', '_blank');
    
    // Track changelog view
    if (typeof gtag !== 'undefined') {
        gtag('event', 'changelog_view', {
            event_category: 'engagement'
        });
    }
}

// Contact form submission
function submitContactForm(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    
    // Add loading state
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.innerHTML = '<span class="btn-icon">⏳</span> שולח...';
    submitButton.disabled = true;
    
    // Simulate form submission (replace with real endpoint)
    setTimeout(() => {
        console.log('Contact form data:', data);
        
        // Show success message
        showNotification('ההודעה נשלחה בהצלחה! נחזור אליך בהקדם.', 'success');
        
        // Reset form
        form.reset();
        
        // Reset button
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
        
        // Track form submission
        if (typeof gtag !== 'undefined') {
            gtag('event', 'contact_form_submit', {
                event_category: 'lead',
                event_label: data.subject
            });
        }
    }, 1500);
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        max-width: 400px;
        font-size: 0.9rem;
        animation: slideInFromRight 0.3s ease;
    `;
    
    // Add to body
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.style.animation = 'slideOutToRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

// Add animation styles
if (!document.querySelector('#notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        @keyframes slideInFromRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOutToRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
        
        .notification-close {
            background: none;
            border: none;
            color: white;
            font-size: 1.2rem;
            cursor: pointer;
            padding: 0;
            margin-right: 0.5rem;
        }
        
        .notification-close:hover {
            opacity: 0.7;
        }
    `;
    document.head.appendChild(style);
}

// Analytics and tracking functions
function trackEvent(eventName, eventData = {}) {
    // Google Analytics 4
    if (typeof gtag !== 'undefined') {
        gtag('event', eventName, eventData);
    }
    
    // Console log for development
    console.log('Event tracked:', eventName, eventData);
}

// Error handling
window.addEventListener('error', function(event) {
    console.error('JavaScript error:', event.error);
    
    // Track errors (optional)
    if (typeof gtag !== 'undefined') {
        gtag('event', 'javascript_error', {
            event_category: 'error',
            event_label: event.error.message
        });
    }
});

// Page visibility API for analytics
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        trackEvent('page_hidden');
    } else {
        trackEvent('page_visible');
    }
});

// Export functions for global access
window.openDemo = openDemo;
window.closeDemo = closeDemo;
window.openChangelog = openChangelog;
window.downloadLatest = downloadLatest;
window.submitContactForm = submitContactForm;