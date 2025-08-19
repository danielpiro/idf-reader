// Global variables

// DOM Content Loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeWebsite();
  setupEventListeners();
  animateCounters();
  initializeAccessibility();
});

// Initialize website
function initializeWebsite() {
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
  // Navigation toggle with accessibility
  const navToggle = document.getElementById("navToggle");
  const navMenu = document.getElementById("navMenu");

  if (navToggle && navMenu) {
    // Toggle menu function
    const toggleMenu = () => {
      const isExpanded = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", !isExpanded);
      navMenu.classList.toggle("active");

      // Prevent body scroll when menu is open
      document.body.style.overflow = isExpanded ? "" : "hidden";

      // Announce to screen readers
      announceToScreenReader(
        isExpanded ? "תפריט הניווט נסגר" : "תפריט הניווט נפתח"
      );
    };

    // Click handler
    navToggle.addEventListener("click", toggleMenu);

    // Touch events for better mobile interaction
    let touchStartY = 0;
    navToggle.addEventListener(
      "touchstart",
      (e) => {
        touchStartY = e.touches[0].clientY;
      },
      { passive: true }
    );

    navToggle.addEventListener("touchend", (e) => {
      const touchEndY = e.changedTouches[0].clientY;
      const touchDiff = Math.abs(touchEndY - touchStartY);

      // Only trigger if it's a tap (not a scroll)
      if (touchDiff < 10) {
        e.preventDefault();
        toggleMenu();
      }
    });

    // Keyboard navigation for mobile menu
    navToggle.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleMenu();
      }
      if (e.key === "Escape") {
        navMenu.classList.remove("active");
        navToggle.setAttribute("aria-expanded", "false");
        document.body.style.overflow = "";
      }
    });

    // Close menu when clicking outside
    document.addEventListener("click", (e) => {
      if (!navToggle.contains(e.target) && !navMenu.contains(e.target)) {
        navMenu.classList.remove("active");
        navToggle.setAttribute("aria-expanded", "false");
        document.body.style.overflow = "";
      }
    });

    // Close menu on window resize to desktop
    window.addEventListener("resize", () => {
      if (window.innerWidth > 768) {
        navMenu.classList.remove("active");
        navToggle.setAttribute("aria-expanded", "false");
        document.body.style.overflow = "";
      }
    });
  }

  // Close mobile menu when clicking on a link
  const navLinks = document.querySelectorAll(".nav-link");
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      navMenu?.classList.remove("active");
      navToggle?.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    });

    // Update aria-current for navigation
    link.addEventListener("click", (e) => {
      navLinks.forEach((l) => l.removeAttribute("aria-current"));
      e.target.setAttribute("aria-current", "page");
    });

    // Add touch feedback
    link.addEventListener(
      "touchstart",
      () => {
        link.style.transform = "scale(0.98)";
      },
      { passive: true }
    );

    link.addEventListener("touchend", () => {
      link.style.transform = "";
    });
  });

  // Add touch feedback to buttons
  const buttons = document.querySelectorAll(".btn");
  buttons.forEach((button) => {
    button.addEventListener(
      "touchstart",
      () => {
        button.style.transform = "scale(0.98)";
      },
      { passive: true }
    );

    button.addEventListener("touchend", () => {
      button.style.transform = "";
    });

    button.addEventListener("touchcancel", () => {
      button.style.transform = "";
    });
  });
}

// Format number with commas
function formatNumber(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Download latest version
async function downloadLatest() {
  // Track download
  if (typeof gtag !== "undefined") {
    gtag("event", "download", {
      event_category: "software",
      event_label: "idf-reader",
    });
  }

  try {
    // Show loading message
    showNotification("מחפש את הגרסה האחרונה...", "info");

    let downloadUrl = null;
    let fileName = null;
    let fileSize = null;

    // Try to get version info from local version.json first (faster)
    try {
      const versionResponse = await fetch("./version.json");
      if (versionResponse.ok) {
        const versionData = await versionResponse.json();
        downloadUrl = versionData.download_url;
        fileName = `idf-reader-${versionData.version}.exe`;
        fileSize = versionData.file_size_mb;
      }
    } catch (versionError) {
      console.log(
        "Local version info not available, falling back to GitHub API"
      );
    }

    // Fallback to GitHub API if local version info not available
    if (!downloadUrl) {
      const response = await fetch(
        "https://api.github.com/repos/danielpiro/idf-reader/releases/latest"
      );

      if (!response.ok) {
        throw new Error("Failed to fetch release info");
      }

      const releaseData = await response.json();

      // Find the executable file in assets
      const exeAsset = releaseData.assets.find(
        (asset) =>
          asset.name.endsWith(".exe") && asset.name.includes("idf-reader")
      );

      if (exeAsset) {
        downloadUrl = exeAsset.browser_download_url;
        fileName = exeAsset.name;
        fileSize = (exeAsset.size / 1024 / 1024).toFixed(1);
      } else {
        throw new Error("No executable found in latest release");
      }
    }

    if (downloadUrl) {
      // Create download link
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      showNotification(`מוריד ${fileName} (${fileSize} MB)`, "success");
    } else {
      throw new Error("No download URL available");
    }
  } catch (error) {
    console.error("Download error:", error);

    // Fallback: direct link to releases page
    showNotification("מפנה לעמוד ההורדות...", "info");
    window.open(
      "https://github.com/danielpiro/idf-reader/releases/latest",
      "_blank"
    );
  }
}

// Setup smooth scrolling
function setupSmoothScrolling() {
  const links = document.querySelectorAll('a[href^="#"]');

  links.forEach((link) => {
    link.addEventListener("click", function (e) {
      e.preventDefault();

      const targetId = this.getAttribute("href");
      const targetElement = document.querySelector(targetId);

      if (targetElement) {
        const navbarHeight = document.querySelector(".navbar").offsetHeight;
        const targetPosition = targetElement.offsetTop - navbarHeight;

        window.scrollTo({
          top: targetPosition,
          behavior: "smooth",
        });
      }
    });
  });
}

// Setup mobile navigation
function setupMobileNavigation() {
  const navToggle = document.getElementById("navToggle");
  const navMenu = document.getElementById("navMenu");

  if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => {
      navToggle.classList.toggle("active");
      navMenu.classList.toggle("active");
    });
  }
}

// Setup pricing toggle
function setupPricingToggle() {
  const pricingToggle = document.getElementById("pricingToggle");

  if (pricingToggle) {
    pricingToggle.addEventListener("change", function () {
      const monthlyElements = document.querySelectorAll(
        ".monthly-price, .monthly-period"
      );
      const yearlyElements = document.querySelectorAll(
        ".yearly-price, .yearly-period"
      );

      if (this.checked) {
        // Show yearly pricing
        monthlyElements.forEach((el) => (el.style.display = "none"));
        yearlyElements.forEach((el) => (el.style.display = "inline"));
      } else {
        // Show monthly pricing
        monthlyElements.forEach((el) => (el.style.display = "inline"));
        yearlyElements.forEach((el) => (el.style.display = "none"));
      }
    });
  }
}

// Setup scroll effects
function setupScrollEffects() {
  const navbar = document.querySelector(".navbar");

  window.addEventListener("scroll", () => {
    if (window.scrollY > 100) {
      navbar.style.background = "rgba(255, 255, 255, 0.98)";
      navbar.style.boxShadow = "0 2px 20px rgba(0, 0, 0, 0.1)";
    } else {
      navbar.style.background = "rgba(255, 255, 255, 0.95)";
      navbar.style.boxShadow = "none";
    }
  });

  // Intersection Observer for animations
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -50px 0px",
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = "1";
        entry.target.style.transform = "translateY(0)";
      }
    });
  }, observerOptions);

  // Observe elements for animation
  const animatedElements = document.querySelectorAll(
    ".feature-card, .pricing-card"
  );
  animatedElements.forEach((el) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(30px)";
    el.style.transition = "opacity 0.6s ease, transform 0.6s ease";
    observer.observe(el);
  });
}

// Animate counters
function animateCounters() {
  const counters = document.querySelectorAll(".stat-number");

  const animateCounter = (counter) => {
    const target = parseInt(counter.textContent.replace(/[^\d]/g, ""));
    const duration = 2000; // 2 seconds
    const start = performance.now();

    const updateCounter = (currentTime) => {
      const elapsed = currentTime - start;
      const progress = Math.min(elapsed / duration, 1);

      const current = Math.floor(progress * target);
      const originalText = counter.textContent;
      const suffix = originalText.replace(/[\d,]/g, "");

      counter.textContent = formatNumber(current) + suffix;

      if (progress < 1) {
        requestAnimationFrame(updateCounter);
      }
    };

    requestAnimationFrame(updateCounter);
  };

  // Intersection Observer for counters
  const counterObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          counterObserver.unobserve(entry.target); // Only animate once
        }
      });
    },
    { threshold: 0.5 }
  );

  counters.forEach((counter) => {
    counterObserver.observe(counter);
  });
}

// Contact form submission with validation
function submitContactForm(event) {
  event.preventDefault();

  const form = event.target;

  // Validate form before submission
  if (!validateForm(form)) {
    announceToScreenReader("יש שגיאות בטופס. אנא תקן את השדות המסומנים.");
    return;
  }

  const formData = new FormData(form);
  const data = Object.fromEntries(formData);

  // Add loading state
  const submitButton = form.querySelector('button[type="submit"]');
  const originalText = submitButton.innerHTML;
  submitButton.innerHTML =
    '<span class="btn-icon" aria-hidden="true">⏳</span> שולח...';
  submitButton.disabled = true;
  submitButton.setAttribute("aria-busy", "true");

  // Simulate form submission (replace with real endpoint)
  setTimeout(() => {
    console.log("Contact form data:", data);

    // Show success message
    showNotification("ההודעה נשלחה בהצלחה! נחזור אליך בהקדם.", "success");

    // Reset form
    form.reset();

    // Reset button
    submitButton.innerHTML = originalText;
    submitButton.disabled = false;

    // Track form submission
    if (typeof gtag !== "undefined") {
      gtag("event", "contact_form_submit", {
        event_category: "lead",
        event_label: data.subject,
      });
    }
  }, 1500);
}

// Show notification
function showNotification(message, type = "info") {
  // Create notification element
  const notification = document.createElement("div");
  notification.className = `notification notification-${type}`;
  notification.innerHTML = `
        <span class="notification-icon">${
          type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️"
        }</span>
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;

  // Add styles
  notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${
          type === "success"
            ? "#10b981"
            : type === "error"
            ? "#ef4444"
            : "#3b82f6"
        };
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
      notification.style.animation = "slideOutToRight 0.3s ease";
      setTimeout(() => notification.remove(), 300);
    }
  }, 5000);
}

// Add animation styles
if (!document.querySelector("#notification-styles")) {
  const style = document.createElement("style");
  style.id = "notification-styles";
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
  if (typeof gtag !== "undefined") {
    gtag("event", eventName, eventData);
  }

  // Console log for development
  console.log("Event tracked:", eventName, eventData);
}

// Error handling
window.addEventListener("error", function (event) {
  console.error("JavaScript error:", event.error);

  // Track errors (optional)
  if (typeof gtag !== "undefined") {
    gtag("event", "javascript_error", {
      event_category: "error",
      event_label: event.error.message,
    });
  }
});

// Page visibility API for analytics
document.addEventListener("visibilitychange", function () {
  if (document.hidden) {
    trackEvent("page_hidden");
  } else {
    trackEvent("page_visible");
  }
});

// Accessibility helper functions
function announceToScreenReader(message) {
  const announcement = document.getElementById("sr-announcements");
  if (announcement) {
    announcement.textContent = message;
    // Clear after 3 seconds
    setTimeout(() => {
      announcement.textContent = "";
    }, 3000);
  }
}

function validateForm(form) {
  let isValid = true;

  // Clear previous errors
  const errorMessages = form.querySelectorAll(".error-message");
  errorMessages.forEach((error) => {
    error.classList.remove("show");
    error.textContent = "";
  });

  const inputs = form.querySelectorAll("input, select, textarea");
  inputs.forEach((input) => {
    input.classList.remove("error");
  });

  // Validate required fields
  const requiredFields = form.querySelectorAll("[required]");
  requiredFields.forEach((field) => {
    if (!field.value.trim()) {
      showFieldError(field, "שדה זה הוא חובה");
      isValid = false;
    }
  });

  // Validate email
  const emailField = form.querySelector('input[type="email"]');
  if (emailField && emailField.value.trim()) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(emailField.value.trim())) {
      showFieldError(emailField, "כתובת אימייל לא תקינה");
      isValid = false;
    }
  }

  // Focus on first error field
  if (!isValid) {
    const firstError = form.querySelector(".error");
    if (firstError) {
      firstError.focus();
    }
  }

  return isValid;
}

function showFieldError(field, message) {
  field.classList.add("error");
  const errorId = field
    .getAttribute("aria-describedby")
    .split(" ")
    .find((id) => id.includes("error"));
  const errorElement = document.getElementById(errorId);
  if (errorElement) {
    errorElement.textContent = message;
    errorElement.classList.add("show");
  }
}

// Keyboard navigation helpers
function setupKeyboardNavigation() {
  // Add keyboard navigation to pricing cards
  const pricingCards = document.querySelectorAll(".pricing-card");
  pricingCards.forEach((card) => {
    card.setAttribute("tabindex", "0");
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        const button = card.querySelector(".btn");
        if (button) {
          button.click();
        }
      }
    });
  });
}

// Initialize accessibility features
function initializeAccessibility() {
  setupKeyboardNavigation();

  // Add live region for dynamic content updates
  const liveRegion = document.createElement("div");
  liveRegion.setAttribute("aria-live", "polite");
  liveRegion.setAttribute("aria-atomic", "true");
  liveRegion.className = "sr-only";
  liveRegion.id = "live-region";
  document.body.appendChild(liveRegion);

  // Announce page load
  setTimeout(() => {
    announceToScreenReader("עמוד IDF Reader נטען בהצלחה");
  }, 1000);
}

// Export functions for global access
window.downloadLatest = downloadLatest;
window.submitContactForm = submitContactForm;
window.announceToScreenReader = announceToScreenReader;
