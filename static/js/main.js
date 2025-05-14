/**
 * Main JavaScript for AI Therapist application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Tab navigation
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            
            // Remove active class from all tabs and content
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to current tab and content
            this.classList.add('active');
            document.getElementById(`${tabId}-tab`).classList.add('active');
            
            // Run tab-specific initialization if needed
            if (window.tabInitializers && window.tabInitializers[tabId]) {
                window.tabInitializers[tabId]();
            }
        });
    });
    
    // Handle Find Therapists links
    const therapistLinks = document.querySelectorAll('a[href^="/find-therapists"]');
    therapistLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Store any filter parameters in session storage for use on the therapists page
            const url = new URL(this.href, window.location.origin);
            const params = url.searchParams;
            
            if (params.has('filter')) {
                sessionStorage.setItem('therapist_filter', params.get('filter'));
            }
        });
    });
    
    // Check for location permissions
    function checkLocationPermission() {
        return new Promise((resolve) => {
            if (!navigator.geolocation) {
                resolve(false);
                return;
            }
            
            navigator.permissions.query({ name: 'geolocation' })
                .then(permissionStatus => {
                    resolve(permissionStatus.state === 'granted');
                })
                .catch(() => {
                    // If permissions API is not supported, we'll assume permission is not granted
                    resolve(false);
                });
        });
    }
    
    // If we're on the therapists tab, check location permission
    const therapistsTab = document.querySelector('.tab[data-tab="therapists"]');
    if (therapistsTab) {
        therapistsTab.addEventListener('click', async function() {
            const hasPermission = await checkLocationPermission();
            
            // If we don't have permission, show a notification
            if (!hasPermission) {
                const notificationElement = document.createElement('div');
                notificationElement.className = 'location-notification';
                notificationElement.innerHTML = `
                    <i class="fas fa-map-marker-alt"></i>
                    <p>You'll need to grant location access to find therapists near you.</p>
                    <button class="dismiss-btn">Got it</button>
                `;
                
                // Add to page
                const container = document.querySelector('.therapists-container');
                if (container && !container.querySelector('.location-notification')) {
                    container.insertBefore(notificationElement, container.firstChild);
                    
                    // Set up dismiss button
                    const dismissBtn = notificationElement.querySelector('.dismiss-btn');
                    if (dismissBtn) {
                        dismissBtn.addEventListener('click', function() {
                            notificationElement.classList.add('dismissing');
                            setTimeout(() => {
                                notificationElement.remove();
                            }, 300);
                        });
                    }
                }
            }
        });
    }
    
    // Set up global window.tabInitializers if not already defined
    if (typeof window.tabInitializers === 'undefined') {
        window.tabInitializers = {};
    }
    
    // Add initializer for therapists tab
    window.tabInitializers.therapists = function() {
        console.log('Initializing therapists tab');
        // No special initialization needed for now
    };
}); 