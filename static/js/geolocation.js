/**
 * Enhanced Geolocation service for AI Therapist application
 * Gets user location for finding nearby therapists with additional features
 */

// Location storage key in localStorage
const LOCATION_STORAGE_KEY = 'ai_therapist_user_location';

/**
 * Get the user's current location using the browser's Geolocation API
 * @param {Object} options - Additional options including callbacks
 * @returns {Promise} Promise that resolves with the location coordinates or rejects with an error
 */
function getUserLocation(options = {}) {
  const {
    onSuccess = null,
    onError = null,
    maxAge = 3600000, // Default max age is 1 hour
    highAccuracy = true,
    timeout = 10000,
    useCached = true,
    forceFresh = false
  } = options;
  
  return new Promise((resolve, reject) => {
    // Check if the browser supports geolocation
    if (!navigator.geolocation) {
      const error = new Error('Geolocation is not supported by your browser');
      if (onError) onError(error);
      reject(error);
      return;
    }

    // Check if we have a cached location that's not too old
    if (useCached && !forceFresh) {
      const savedLocation = getSavedLocation(maxAge);
      if (savedLocation) {
        console.log('Using saved location from localStorage');
        if (onSuccess) onSuccess(savedLocation);
        resolve(savedLocation);
        return;
      }
    }

    // Options for the geolocation request
    const geoOptions = {
      enableHighAccuracy: highAccuracy,
      timeout: timeout,
      maximumAge: maxAge
    };

    // Get current position
    navigator.geolocation.getCurrentPosition(
      // Success callback
      (position) => {
        const locationData = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: Date.now()
        };

        // Save location to localStorage
        saveLocation(locationData);
        
        // Trigger success callback if provided
        if (onSuccess) onSuccess(locationData);
        
        // Resolve the promise with the location data
        resolve(locationData);
        
        // Dispatch a custom event that other components can listen to
        const locationEvent = new CustomEvent('location:updated', { 
          detail: locationData 
        });
        document.dispatchEvent(locationEvent);
      },
      // Error callback
      (error) => {
        console.error('Error getting location:', error.message);
        
        // Trigger error callback if provided
        if (onError) onError(error);
        
        // Dispatch error event
        const errorEvent = new CustomEvent('location:error', { 
          detail: { 
            code: error.code,
            message: error.message
          }
        });
        document.dispatchEvent(errorEvent);
        
        reject(error);
      },
      // Options
      geoOptions
    );
  });
}

/**
 * Save location data to localStorage
 * @param {Object} locationData - Object containing latitude, longitude and timestamp
 */
function saveLocation(locationData) {
  try {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(locationData));
    console.log('Location saved to localStorage');
    
    // Dispatch a custom event when location is saved
    const savedEvent = new CustomEvent('location:saved', { 
      detail: locationData 
    });
    document.dispatchEvent(savedEvent);
  } catch (error) {
    console.error('Error saving location to localStorage:', error);
  }
}

/**
 * Get saved location from localStorage if it exists and is not too old
 * @param {Number} maxAge - Maximum age of the cached location in milliseconds
 * @returns {Object|null} Location data or null if no valid saved location
 */
function getSavedLocation(maxAge = 3600000) {
  try {
    const savedLocationString = localStorage.getItem(LOCATION_STORAGE_KEY);
    if (!savedLocationString) return null;

    const savedLocation = JSON.parse(savedLocationString);
    const now = Date.now();

    // Check if saved location is not too old
    if (savedLocation && savedLocation.timestamp && (now - savedLocation.timestamp < maxAge)) {
      return savedLocation;
    }
    
    return null;
  } catch (error) {
    console.error('Error reading saved location:', error);
    return null;
  }
}

/**
 * Clear saved location from localStorage
 */
function clearSavedLocation() {
  try {
    localStorage.removeItem(LOCATION_STORAGE_KEY);
    console.log('Saved location cleared from localStorage');
    
    // Dispatch a custom event when location is cleared
    const clearedEvent = new CustomEvent('location:cleared');
    document.dispatchEvent(clearedEvent);
  } catch (error) {
    console.error('Error clearing saved location from localStorage:', error);
  }
}

/**
 * Check if the app has geolocation permission
 * @returns {Promise} Promise that resolves with the permission state ('granted', 'denied', or 'prompt')
 */
function checkGeolocationPermission() {
  return new Promise((resolve) => {
    if (!navigator.permissions) {
      // Permissions API not supported, resolve with 'unknown'
      resolve('unknown');
      return;
    }
    
    navigator.permissions.query({ name: 'geolocation' })
      .then(permissionStatus => {
        resolve(permissionStatus.state);
        
        // Listen for changes to the permission
        permissionStatus.onchange = () => {
          // Dispatch a custom event when permission changes
          const permEvent = new CustomEvent('location:permission-changed', { 
            detail: { state: permissionStatus.state } 
          });
          document.dispatchEvent(permEvent);
        };
      })
      .catch(error => {
        console.error('Error checking geolocation permission:', error);
        resolve('unknown');
      });
  });
}

/**
 * Calculate distance between two coordinates using the Haversine formula
 * @param {Number} lat1 - Latitude of first point
 * @param {Number} lon1 - Longitude of first point
 * @param {Number} lat2 - Latitude of second point
 * @param {Number} lon2 - Longitude of second point
 * @returns {Number} Distance in miles
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
  // Convert degrees to radians
  const toRad = (value) => value * Math.PI / 180;
  
  // Earth radius in miles
  const R = 3958.8;
  
  // Haversine formula
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * 
            Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  const distance = R * c;
  
  return distance;
}

/**
 * Fetch nearby therapists based on user location
 * @param {Object} options - Options for the API request
 * @returns {Promise} Promise that resolves with therapist data or rejects with an error
 */
function fetchNearbyTherapists(options = {}) {
  const {
    maxDistance = 10,           // Miles
    specialty = 'all',          // Specialty filter
    insurance = 'all',          // Insurance filter
    availability = 'any',       // Availability filter
    sortBy = 'distance',        // Sort results by (distance, rating)
    limit = 20,                 // Maximum number of results
    onLoadingStart = null,      // Callback when loading starts
    onLoadingEnd = null,        // Callback when loading ends
    onSuccess = null,           // Callback on success
    onError = null              // Callback on error
  } = options;
  
  return new Promise((resolve, reject) => {
    // Show loading indicator
    if (onLoadingStart) onLoadingStart();
    
    const loadingEvent = new CustomEvent('nearbyTherapists:loading');
    document.dispatchEvent(loadingEvent);
    
    // Get user location
    getUserLocation()
      .then(location => {
        // Build query parameters
        const params = new URLSearchParams({
          lat: location.latitude,
          lng: location.longitude,
          distance: maxDistance
        });
        
        // Add optional filters
        if (specialty !== 'all') params.append('specialty', specialty);
        if (insurance !== 'all') params.append('insurance', insurance);
        if (availability !== 'any') params.append('availability', availability);
        if (sortBy) params.append('sort', sortBy);
        if (limit) params.append('limit', limit);
        
        // Create the URL
        const url = `/nearby_therapists?${params.toString()}`;
        
        // Fetch nearby therapists
        return fetch(url);
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        // End loading
        if (onLoadingEnd) onLoadingEnd();
        
        // Dispatch success event with the data
        const successEvent = new CustomEvent('nearbyTherapists:success', { detail: data });
        document.dispatchEvent(successEvent);
        
        // Call success callback
        if (onSuccess) onSuccess(data);
        
        resolve(data);
      })
      .catch(error => {
        console.error('Error fetching nearby therapists:', error);
        
        // End loading
        if (onLoadingEnd) onLoadingEnd();
        
        // Dispatch error event
        const errorEvent = new CustomEvent('nearbyTherapists:error', { detail: error.message });
        document.dispatchEvent(errorEvent);
        
        // Call error callback
        if (onError) onError(error);
        
        reject(error);
      });
  });
}

/**
 * Initialize geolocation features
 * Call this function to set up event listeners for UI elements
 */
function initGeolocation() {
  // Find therapist buttons in the UI
  const findTherapistButtons = document.querySelectorAll('.find-therapist-btn');
  
  // Add click event listeners to all find therapist buttons
  findTherapistButtons.forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      
      // Update button state
      button.disabled = true;
      const originalHTML = button.innerHTML;
      button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Finding therapists...';
      
      // Fetch nearby therapists
      fetchNearbyTherapists({
        onLoadingStart: () => {
          console.log('Loading nearby therapists...');
        },
        onLoadingEnd: () => {
          // Reset button state
          button.disabled = false;
          button.innerHTML = originalHTML;
        },
        onSuccess: (data) => {
          console.log('Therapists found:', data);
          // Either redirect or show results
          if (window.location.pathname !== '/find-therapists') {
            window.location.href = '/find-therapists';
          }
        },
        onError: (error) => {
          console.error('Error finding therapists:', error);
          // Show error message
          displayErrorMessage(error.message || 'Could not find nearby therapists. Please try again.');
        }
      });
    });
  });
  
  // Refresh location buttons
  const refreshLocationButtons = document.querySelectorAll('.refresh-location-btn');
  refreshLocationButtons.forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      
      // Clear cached location
      clearSavedLocation();
      
      // Get fresh location
      getUserLocation({ 
        forceFresh: true,
        onSuccess: (location) => {
          // Show success message
          const successEvent = new CustomEvent('location:refresh-success', { 
            detail: location 
          });
          document.dispatchEvent(successEvent);
        },
        onError: (error) => {
          // Show error message
          const errorEvent = new CustomEvent('location:refresh-error', { 
            detail: error 
          });
          document.dispatchEvent(errorEvent);
        }
      });
    });
  });
  
  // Listen for custom events
  document.addEventListener('nearbyTherapists:loading', () => {
    console.log('Loading nearby therapists...');
  });
  
  document.addEventListener('nearbyTherapists:success', (event) => {
    console.log('Therapists found:', event.detail);
  });
  
  document.addEventListener('nearbyTherapists:error', (event) => {
    console.error('Error:', event.detail);
  });
}

/**
 * Display an error message in the UI
 * @param {String} message - Error message to display
 */
function displayErrorMessage(message) {
  // Check if an error container already exists
  let errorContainer = document.getElementById('location-error');
  
  if (!errorContainer) {
    // Create error container
    errorContainer = document.createElement('div');
    errorContainer.id = 'location-error';
    errorContainer.className = 'error-message';
    
    // Insert at appropriate place
    const contentArea = document.querySelector('.content-area') || document.body;
    contentArea.appendChild(errorContainer);
  }
  
  // Set error message content
  errorContainer.innerHTML = `
    <i class="fas fa-exclamation-circle"></i>
    <p>${message}</p>
    <p>Please enable location services in your browser settings and try again.</p>
    <button id="dismiss-error" class="dismiss-btn">Dismiss</button>
  `;
  
  // Add dismiss button functionality
  const dismissBtn = errorContainer.querySelector('#dismiss-error');
  if (dismissBtn) {
    dismissBtn.addEventListener('click', () => {
      errorContainer.style.display = 'none';
    });
  }
  
  // Show the container
  errorContainer.style.display = 'block';
}

// Export functions for use in other scripts
window.aiTherapistGeo = {
  getUserLocation,
  getSavedLocation,
  saveLocation,
  clearSavedLocation,
  checkGeolocationPermission,
  calculateDistance,
  fetchNearbyTherapists,
  initGeolocation
};

// Initialize geolocation features when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initGeolocation); 