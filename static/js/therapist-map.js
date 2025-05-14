// Therapist Map Integration using Google Maps
document.addEventListener('DOMContentLoaded', function() {
    // Global variables to track initialization state
    window.mapInitialized = false;
    window.therapistsLoaded = false;
    
    // Variables
    let map = null;
    let userMarker = null;
    let therapistMarkers = [];
    let currentTherapist = null;
    let userLocation = null;
    let therapistCache = {};
    let infoWindows = [];
    let placesService = null;
    let geocoder = null;
    let bounds = null;
    
    // Main page variables (moved to global scope)
    let mainPageMap = null;
    let mainPageUserMarker = null;
    let mainPageTherapistMarkers = [];
    let mainPageInfoWindows = [];
    let mainPageUserLocation = null;
    let mainPageGeocoder = null;
    let mainPagePlacesService = null;
    let mainPageBounds = null;
    
    // DOM Elements
    const therapistMap = document.getElementById('therapistMap');
    const therapistList = document.getElementById('therapistList');
    const therapistDetails = document.getElementById('therapistDetails');
    const locationSearch = document.getElementById('therapistLocationSearch');
    const specialtyFilter = document.getElementById('specialtyFilter');
    const findTherapistsBtn = document.getElementById('findTherapistsBtn');
    const detectLocationBtn = document.getElementById('detectLocationBtn');
    
    // Initialize Google Maps
    window.initMap = function() {
        try {
            console.log("initMap called - initializing maps");
            window.mapInitialized = true;
            
            // Check if we're on the main page or the dedicated therapist page
            const isMainPage = window.location.pathname === '/' || window.location.pathname === '/index';
            const isDedicatedPage = window.location.pathname === '/nearby_therapists' || window.location.pathname === '/find-therapists';
            
            if (isMainPage) {
                console.log("Initializing map on main page");
                initializeMainPageMap();
            } else if (isDedicatedPage) {
                console.log("Initializing map on dedicated therapist page");
                // The rest of the code in this function will handle the dedicated page
                // Create a default map centered on the US
                const defaultLocation = { lat: 37.0902, lng: -95.7129 };
                
                map = new google.maps.Map(therapistMap, {
                    center: defaultLocation,
                    zoom: 4,
                    mapTypeControl: false,
                    streetViewControl: false,
                    fullscreenControl: true
                });
                
                // Initialize Places service
                placesService = new google.maps.places.PlacesService(map);
                
                // Initialize Geocoder
                geocoder = new google.maps.Geocoder();
                
                // Create bounds object
                bounds = new google.maps.LatLngBounds();
                
                // Initialize search box using Places Autocomplete
                if (locationSearch) {
                    const autocomplete = new google.maps.places.Autocomplete(locationSearch, {
                        types: ['geocode']
                    });
                    
                    autocomplete.addListener('place_changed', function() {
                        const place = autocomplete.getPlace();
                        if (place.geometry) {
                            userLocation = {
                                latitude: place.geometry.location.lat(),
                                longitude: place.geometry.location.lng()
                            };
                            updateUserLocationOnMap();
                        }
                    });
                }
                
                // Add event listeners for buttons
                if (findTherapistsBtn) {
                    findTherapistsBtn.addEventListener('click', searchTherapists);
                }
                
                if (detectLocationBtn) {
                    detectLocationBtn.addEventListener('click', detectUserLocation);
                }
                
                // Check if geolocation is supported
                if (!navigator.geolocation) {
                    console.log("Geolocation not supported - hiding detect location button");
                    if (detectLocationBtn) {
                        detectLocationBtn.style.display = 'none';
                    }
                }
                
                // Add event listener for window resize to ensure map resizes correctly
                window.addEventListener('resize', function() {
                    if (map) {
                        google.maps.event.trigger(map, 'resize');
                        if (bounds && !bounds.isEmpty()) {
                            map.fitBounds(bounds);
                        }
                    }
                });
            } else {
                console.log("Not on a page with a map");
            }
        } catch (error) {
            console.error("Error initializing map:", error);
            window.mapInitialized = false;
            
            // Show error in the map container for visibility
            if (therapistMap) {
                therapistMap.innerHTML = `
                    <div style="padding: 20px; color: red; text-align: center;">
                        <h3>Error Loading Google Maps</h3>
                        <p>${error.message}</p>
                        <p>Please check the console for more details.</p>
                    </div>
                `;
            }
        }
    };
    
    // Add a function to check map initialization and retry if needed
    function ensureMapInitialized(callback, maxRetries = 5, delay = 500) {
        let retries = 0;
        
        function checkAndRetry() {
            if (window.mapInitialized && map && google && google.maps) {
                console.log("Map is initialized, proceeding with callback");
                callback();
                return;
            }
            
            retries++;
            if (retries >= maxRetries) {
                console.error("Max retries reached, map initialization failed");
                return;
            }
            
            console.log(`Map not yet initialized, retrying (${retries}/${maxRetries})...`);
            setTimeout(checkAndRetry, delay);
        }
        
        checkAndRetry();
    }
    
    // Detect user location using browser geolocation API
    function detectUserLocation() {
        // Only proceed if geolocation is available
        if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser");
            return;
        }
        
        // Show loading spinner in the button
        if (detectLocationBtn) {
            detectLocationBtn.innerHTML = '<i class="fas fa-spinner location-spinner"></i>';
            detectLocationBtn.disabled = true;
        }
        
        // Get the current position
        navigator.geolocation.getCurrentPosition(
            // Success callback
            function(position) {
                console.log("Got user location:", position.coords);
                
                // Reset button
                if (detectLocationBtn) {
                    detectLocationBtn.innerHTML = '<i class="fas fa-crosshairs"></i>';
                    detectLocationBtn.disabled = false;
                }
                
                // Store the location
                userLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                
                // Update the map
                updateUserLocationOnMap();
                
                // Try to get an address for the detected location
                reverseGeocode(position.coords.latitude, position.coords.longitude);
                
                // Automatically search for therapists near this location
                ensureMapInitialized(function() {
                    fetchTherapists(userLocation.latitude, userLocation.longitude);
                });
            },
            // Error callback
            function(error) {
                // Reset button
                if (detectLocationBtn) {
                    detectLocationBtn.innerHTML = '<i class="fas fa-crosshairs"></i>';
                    detectLocationBtn.disabled = false;
                }
                
                console.error("Error getting location:", error);
                
                let errorMessage = "Unable to retrieve your location. ";
                
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMessage += "You denied the request for geolocation.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errorMessage += "Location information is unavailable.";
                        break;
                    case error.TIMEOUT:
                        errorMessage += "The request to get your location timed out.";
                        break;
                    case error.UNKNOWN_ERROR:
                        errorMessage += "An unknown error occurred.";
                        break;
                }
                
                alert(errorMessage);
            },
            // Options
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }
    
    // Reverse geocode coordinates to get an address
    function reverseGeocode(lat, lng) {
        if (!geocoder) return;
        
        const latlng = { lat: lat, lng: lng };
        
        geocoder.geocode({ 'location': latlng }, function(results, status) {
            if (status === 'OK') {
                if (results[0] && locationSearch) {
                    // Update the search input with the formatted address
                    locationSearch.value = results[0].formatted_address;
                }
            } else {
                console.error('Geocoder failed due to: ' + status);
            }
        });
    }
    
    // Check if Google Maps API failed to load
    window.gm_authFailure = function() {
        console.error("Google Maps authentication failed");
        
        // Show error in the map container
        if (therapistMap) {
            therapistMap.innerHTML = `
                <div style="padding: 20px; color: red; text-align: center;">
                    <h3>Google Maps API Error</h3>
                    <p>Invalid API key or Google Maps API couldn't be loaded.</p>
                    <p>Please check your API key and billing status.</p>
                </div>
            `;
        }
    };
    
    // Search for therapists
    function searchTherapists() {
        console.log("searchTherapists called");
        
        // Get location and specialty
        const location = locationSearch ? locationSearch.value : '';
        const specialty = specialtyFilter ? specialtyFilter.value : '';
        
        console.log("Search parameters - Location:", location, "Specialty:", specialty);
        
        if (!location && !userLocation) {
            alert("Please enter a location or use the detect location button");
            return;
        }
        
        // Get distance filter value
        const distanceFilter = document.getElementById('distanceFilter');
        const distance = distanceFilter ? distanceFilter.value : '10';
        
        // Get Gemini toggle value
        const useGemini = document.getElementById('geminiEnabled')?.checked ?? true;
        
        // Show loading state
        therapistList.innerHTML = `
            <div class="therapist-list-placeholder">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Searching for therapists${useGemini ? ' using AI' : ''}...</p>
                ${useGemini ? `
                <div class="gemini-badge">
                    <i class="fas fa-brain"></i> Gemini AI Enhanced Search
                </div>` : ''}
            </div>
        `;
        
        // If userLocation is not set but we have a location string, geocode it
        if (!userLocation && location) {
            ensureMapInitialized(function() {
                geocodeLocation(location, specialty, distance, useGemini);
            });
        } else if (userLocation) {
            // Use existing user location
            fetchTherapists(userLocation.latitude, userLocation.longitude, specialty, useGemini);
        }
    }
    
    // Geocode location string to coordinates
    function geocodeLocation(locationString, specialty, distance = '10', useGemini = true) {
        console.log(`Geocoding location: ${locationString}`);
        
        if (!geocoder) {
            console.error("Geocoder not initialized");
            
            // Show error message
            therapistList.innerHTML = `
                <div class="therapist-list-placeholder">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Google Maps is not fully loaded. Please try again in a moment.</p>
                </div>
            `;
            return;
        }
        
        geocoder.geocode({ 'address': locationString }, function(results, status) {
            if (status === 'OK' && results[0]) {
                const lat = results[0].geometry.location.lat();
                const lng = results[0].geometry.location.lng();
                
                console.log(`Geocoded ${locationString} to (${lat}, ${lng})`);
                
                // Update userLocation
                userLocation = {
                    latitude: lat,
                    longitude: lng
                };
                
                // Update map
                updateUserLocationOnMap();
                
                // Fetch therapists
                fetchTherapists(lat, lng, specialty, useGemini);
            } else {
                console.error('Geocode was not successful for the following reason:', status);
                
                // Show error in the therapist list
                therapistList.innerHTML = `
                    <div class="therapist-list-placeholder">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>We couldn't find that location. Please try again with a different search.</p>
                    </div>
                `;
            }
        });
    }
    
    // Update user location marker on map
    function updateUserLocationOnMap() {
        console.log("Updating user location on map");
        
        ensureMapInitialized(function() {
            if (!map || !userLocation) {
                console.error("Map or user location not available");
                return;
            }
            
            const position = new google.maps.LatLng(userLocation.latitude, userLocation.longitude);
            
            // Create or update user marker
            if (userMarker) {
                userMarker.setPosition(position);
            } else {
                // Create custom user marker
                userMarker = new google.maps.Marker({
                    position: position,
                    map: map,
                    icon: {
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 10,
                        fillColor: '#5B6EF5',
                        fillOpacity: 1,
                        strokeColor: '#ffffff',
                        strokeWeight: 2
                    },
                    title: 'Your Location',
                    zIndex: 1000
                });
                
                // Add info window
                const infoWindow = new google.maps.InfoWindow({
                    content: '<div class="map-popup"><h3>Your Location</h3></div>'
                });
                
                userMarker.addListener('click', function() {
                    infoWindow.open(map, userMarker);
                });
            }
            
            // Center map on user location
            map.setCenter(position);
            map.setZoom(12);
        });
    }
    
    // Fetch therapists from API
    function fetchTherapists(lat, lng, specialty, useGemini = true) {
        console.log(`Fetching therapists at (${lat}, ${lng}) with specialty ${specialty || 'all'}`);
        
        // Create a cache key (include useGemini to separate cached results)
        const cacheKey = `${lat},${lng},${specialty || ''},${useGemini ? 'gemini' : 'standard'}`;
        
        // Check if we have cached data
        if (therapistCache[cacheKey]) {
            console.log('Using cached therapist data');
            displayTherapistResults(therapistCache[cacheKey], useGemini);
            return;
        }
        
        // Use our backend API to get therapist data
        // Fix specialty handling: ensure it's properly passed in the query params
        const specialtyParam = specialty && specialty !== 'all' ? specialty : '';
        
        const searchParams = new URLSearchParams({
            lat: lat,
            lng: lng,
            specialty: specialtyParam,
            use_gemini: useGemini.toString()
        });
        
        console.log("API request URL parameters:", searchParams.toString());
        
        // Show loading state
        therapistList.innerHTML = `
            <div class="therapist-list-placeholder">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Searching for therapists${useGemini ? ' using AI' : ''}...</p>
                ${useGemini ? `
                <div class="gemini-badge">
                    <i class="fas fa-brain"></i> Gemini AI Enhanced Search
                </div>` : ''}
            </div>
        `;
        
        // Fetch therapist data from our API
        fetch(`/api/nearby-therapists?${searchParams.toString()}`)
            .then(response => {
                console.log("API response status:", response.status);
                if (!response.ok) {
                    throw new Error(`Failed to fetch therapists: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("API response data:", data);
                
                if (data && data.results && data.results.length > 0) {
                    console.log(`Received ${data.results.length} therapist results from API`);
                    
                    // Process the data
                    const therapists = processTherapistResults(data.results, lat, lng);
                    console.log("Processed therapist results:", therapists);
                    
                    // Cache the results
                    therapistCache[cacheKey] = therapists;
                    
                    // Display the therapists
                    displayTherapistResults(therapists, useGemini);
                } else {
                    console.log("No therapist results returned from API");
                    // Fall back to sample data if available
                    if (data && data.sample_results) {
                        console.log("Using sample results instead");
                        const sampleTherapists = processTherapistResults(data.sample_results, lat, lng);
                        displayTherapistResults(sampleTherapists, false);
                        return;
                    }
                    
                    // No results
                    therapistList.innerHTML = `
                        <div class="therapist-list-placeholder">
                            <i class="fas fa-user-md"></i>
                            <p>No therapists found in this area. Try expanding your search or changing the specialty.</p>
                        </div>
                    `;
                    
                    // Add event listener to retry button
                    document.getElementById('retryWithSample')?.addEventListener('click', function() {
                        // Generate sample data on the client side as a fallback
                        const sampleTherapists = generateSampleTherapists(lat, lng, 10);
                        displayTherapistResults(sampleTherapists, false);
                    });
                }
            })
            .catch(error => {
                console.error('Error fetching therapists:', error);
                therapistList.innerHTML = `
                    <div class="therapist-list-placeholder">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>There was an error finding therapists: ${error.message}</p>
                        <button id="retryButton" class="search-btn" style="margin-top: 15px;">
                            <i class="fas fa-sync"></i> Retry
                        </button>
                    </div>
                `;
                
                // Add event listener to retry button
                document.getElementById('retryButton')?.addEventListener('click', function() {
                    fetchTherapists(lat, lng, specialty, useGemini);
                });
            });
    }
    
    // Function to generate sample therapists on the client side as a fallback
    function generateSampleTherapists(lat, lng, count = 5) {
        console.log("Generating sample therapists as fallback");
        const therapists = [];
        const specialties = ['Anxiety', 'Depression', 'Trauma', 'Relationship', 'CBT', 'Family Therapy'];
        const firstNames = ['Michael', 'Jennifer', 'David', 'Sarah', 'Robert', 'Lisa', 'John', 'Emily'];
        const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller', 'Davis', 'Garcia'];
        
        for (let i = 0; i < count; i++) {
            // Generate random coordinates within ~2 miles
            const randomLat = lat + (Math.random() - 0.5) * 0.03;
            const randomLng = lng + (Math.random() - 0.5) * 0.03;
            
            const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
            const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
            const specialty = specialties[Math.floor(Math.random() * specialties.length)];
            const title = Math.random() > 0.5 ? 'Dr.' : 'LMFT';
            const initials = firstName[0] + lastName[0];
            
            const distance = calculateDistance(lat, lng, randomLat, randomLng);
            
            therapists.push({
                id: `sample-${i}`,
                name: `${title} ${firstName} ${lastName}`,
                specialty: specialty,
                latitude: randomLat,
                longitude: randomLng,
                distance: distance,
                rating: (3.5 + Math.random() * 1.5).toFixed(1),
                reviewCount: Math.floor(Math.random() * 45 + 5),
                phone: `(${Math.floor(Math.random() * 900 + 100)}) ${Math.floor(Math.random() * 900 + 100)}-${Math.floor(Math.random() * 9000 + 1000)}`,
                website: `https://example.com/therapist${i}`,
                address: `${Math.floor(Math.random() * 9000 + 1000)} Main St, Suite ${Math.floor(Math.random() * 900 + 100)}`,
                initials: initials
            });
        }
        
        return therapists;
    }
    
    // Function to handle therapist results and display them
    function displayTherapistResults(therapists, usedGemini = false) {
        console.log(`Displaying ${therapists.length} therapist results`);
        
        // Ensure map is initialized before displaying therapists
        ensureMapInitialized(function() {
            // Display therapists on map and in list
            displayTherapists(therapists, usedGemini);
        });
    }
    
    // Process Google Places API results into our therapist format
    function processTherapistResults(results, userLat, userLng) {
        return results.map(place => {
            const location = place.geometry?.location;
            if (!location) return null;
            
            // Calculate distance
            const distance = calculateDistance(
                userLat, userLng, 
                typeof location.lat === 'function' ? location.lat() : location.lat, 
                typeof location.lng === 'function' ? location.lng() : location.lng
            );
            
            // Extract specialty from types or name
            let specialty = 'Therapy';
            const lowerName = place.name.toLowerCase();
            
            if (lowerName.includes('psychologist') || lowerName.includes('psychology')) {
                specialty = 'Psychology';
            } else if (lowerName.includes('psychiatrist') || lowerName.includes('psychiatry')) {
                specialty = 'Psychiatry';
            } else if (lowerName.includes('marriage') || lowerName.includes('couple')) {
                specialty = 'Couples Therapy';
            } else if (lowerName.includes('child') || lowerName.includes('pediatric')) {
                specialty = 'Child Therapy';
            } else if (lowerName.includes('trauma')) {
                specialty = 'Trauma & PTSD';
            } else if (lowerName.includes('depress')) {
                specialty = 'Depression';
            } else if (lowerName.includes('anxiety')) {
                specialty = 'Anxiety';
            }
            
            // Generate initials from name
            const nameParts = place.name.split(' ');
            let initials = '';
            for (let i = 0; i < Math.min(nameParts.length, 2); i++) {
                if (nameParts[i].length > 0) {
                    initials += nameParts[i][0].toUpperCase();
                }
            }
            if (initials.length === 0) initials = 'T';
            
            // Process reviews if available
            const reviews = place.reviews || [];
            
            // Create our standardized therapist object
            return {
                id: place.place_id || place.id,
                name: place.name,
                specialty: specialty,
                latitude: typeof location.lat === 'function' ? location.lat() : location.lat,
                longitude: typeof location.lng === 'function' ? location.lng() : location.lng,
                distance: distance,
                rating: place.rating || (3.5 + Math.random() * 1.5).toFixed(1),
                reviewCount: place.user_ratings_total || reviews.length,
                phone: place.formatted_phone_number || place.phone || 'Contact for details',
                website: place.website || '#',
                address: place.vicinity || place.formatted_address || place.address || 'Address not available',
                initials: initials,
                reviews: reviews.map(review => ({
                    author: review.author_name || 'Anonymous',
                    date: review.relative_time_description || 'Recent',
                    rating: review.rating || 4,
                    text: review.text || 'No comment provided.'
                }))
            };
        }).filter(Boolean);
    }
    
    // Calculate distance between coordinates
    function calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 3958.8; // Earth's radius in miles
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = 
            Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
            Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        const distance = R * c;
        
        return Math.round(distance * 10) / 10; // Round to 1 decimal place
    }
    
    // Display therapists on map and in list
    function displayTherapists(therapists, usedGemini = false) {
        console.log("displayTherapists called with", therapists.length, "therapists");
        window.therapistsLoaded = true;
        
        // Clear previous markers
        therapistMarkers.forEach(marker => marker.setMap(null));
        therapistMarkers = [];
        
        // Close all info windows
        infoWindows.forEach(infoWindow => infoWindow.close());
        infoWindows = [];
        
        // Clear therapist list
        therapistList.innerHTML = '';
        
        // Hide details panel if shown
        if (therapistDetails) {
            therapistDetails.style.display = 'none';
        }
        
        if (!therapists || therapists.length === 0) {
            therapistList.innerHTML = `
                <div class="no-results">
                    <i class="fas fa-search-minus"></i>
                    <p>No therapists found in this area.</p>
                    <p>Try expanding your search radius or changing location.</p>
                </div>
            `;
            return;
        }
        
        // Get map bounds
        bounds = new google.maps.LatLngBounds();
        
        // Include user location in bounds if available
        if (userMarker) {
            bounds.extend(userMarker.getPosition());
        }
        
        // Process each therapist
        therapists.forEach((therapist, index) => {
            // Get lat & lng from the data
            let lat, lng;
            
            if (therapist.geometry && therapist.geometry.location) {
                // Google Places API format
                lat = therapist.geometry.location.lat;
                lng = therapist.geometry.location.lng;
                
                // Convert to number if needed
                if (typeof lat === 'function') lat = lat();
                if (typeof lng === 'function') lng = lng();
            } else {
                // Custom JSON format
                lat = therapist.latitude;
                lng = therapist.longitude;
            }
            
            if (!lat || !lng) {
                console.warn("No valid location for therapist:", therapist.name);
                return;
            }
            
            // Extract ID 
            const therapistId = therapist.place_id || therapist.id || `t-${index}`;
            
            // Create LatLng for this point
            const position = new google.maps.LatLng(lat, lng);
            
            // Add to bounds
            bounds.extend(position);
            
            // Add marker
            createTherapistMarker(position, therapist, index);
            
            // Get specialty from the data
            let specialty = '';
            if (therapist.specialty) {
                specialty = therapist.specialty;
            } else if (therapist.types && therapist.types.length > 0) {
                const relevantTypes = therapist.types.filter(type => 
                    !['health', 'point_of_interest', 'establishment'].includes(type)
                );
                specialty = relevantTypes.length > 0 ? 
                    relevantTypes.map(t => t.replace(/_/g, ' ')).join(', ') : 
                    'Therapist';
            }
            
            // Calculate distance text
            let distanceText = '';
            if (therapist.distance) {
                distanceText = `${therapist.distance} miles away`;
            } else if (userLocation && lat && lng) {
                const therapistLatLng = new google.maps.LatLng(lat, lng);
                const userLatLng = new google.maps.LatLng(userLocation.lat, userLocation.lng);
                const distance = google.maps.geometry.spherical.computeDistanceBetween(userLatLng, therapistLatLng);
                distanceText = `${(distance / 1609).toFixed(1)} miles away`;
            }
            
            // Get first letter of name for avatar
            const nameFirstLetter = therapist.name ? therapist.name.charAt(0).toUpperCase() : 'T';
            
            // Create HTML for the therapist list item
            const itemHtml = `
                <div class="therapist-item" data-id="${therapistId}">
                    <div class="therapist-item-header">
                        <div class="therapist-avatar">${nameFirstLetter}</div>
                        <div class="therapist-info">
                            <h3 class="therapist-name">${therapist.name}</h3>
                            <div class="therapist-specialty">${specialty}</div>
                            <div class="therapist-distance">${distanceText}</div>
                        </div>
                    </div>
                    <div class="therapist-item-footer">
                        <div class="therapist-rating">
                            ${therapist.rating ? `
                                <div class="stars">
                                    ${generateStars(therapist.rating)}
                                </div>
                                <span class="rating-text">${therapist.rating} (${therapist.user_ratings_total || 0})</span>
                            ` : ''}
                        </div>
                        <button class="btn-view-details">View Details</button>
                    </div>
                </div>
            `;
            
            // Add to list
            therapistList.innerHTML += itemHtml;
        });
        
        // Add event listeners to list items
        document.querySelectorAll('.therapist-item').forEach(item => {
            item.addEventListener('click', function() {
                const id = this.dataset.id;
                const therapist = therapists.find(t => (t.place_id || t.id) === id);
                if (therapist) {
                    selectTherapist(therapist);
                }
            });
        });
        
        // Fit map to bounds
        if (bounds && !bounds.isEmpty() && map) {
            try {
                map.fitBounds(bounds);
                
                // If only one result or very close results, zoom out a bit
                if (therapists.length === 1 || map.getZoom() > 15) {
                    map.setZoom(13);
                }
            } catch (e) {
                console.error("Error fitting bounds:", e);
            }
        }
    }
    
    // Generate star rating HTML
    function generateStars(rating) {
        const fullStars = Math.floor(rating);
        const halfStar = rating % 1 >= 0.5;
        const emptyStars = 5 - fullStars - (halfStar ? 1 : 0);
        
        let html = '';
        
        // Full stars
        for (let i = 0; i < fullStars; i++) {
            html += '<i class="fas fa-star"></i>';
        }
        
        // Half star
        if (halfStar) {
            html += '<i class="fas fa-star-half-alt"></i>';
        }
        
        // Empty stars
        for (let i = 0; i < emptyStars; i++) {
            html += '<i class="far fa-star"></i>';
        }
        
        return html;
    }
    
    // Select a therapist and show details
    function selectTherapist(therapist) {
        console.log("Selecting therapist:", therapist.name);
        
        // Update selected state in list
        const items = therapistList.querySelectorAll('.therapist-item');
        items.forEach(item => {
            item.classList.remove('active');
            if (item.dataset.id === (therapist.id || therapist.place_id)) {
                item.classList.add('active');
                item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });
        
        // Find the marker for this therapist
        let markerFound = false;
        therapistMarkers.forEach((marker, index) => {
            const markerPosition = marker.getPosition();
            const therapistLat = therapist.latitude || 
                (therapist.geometry && therapist.geometry.location && 
                (typeof therapist.geometry.location.lat === 'function' ? 
                    therapist.geometry.location.lat() : therapist.geometry.location.lat));
            
            const therapistLng = therapist.longitude || 
                (therapist.geometry && therapist.geometry.location && 
                (typeof therapist.geometry.location.lng === 'function' ? 
                    therapist.geometry.location.lng() : therapist.geometry.location.lng));
            
            if (markerPosition.lat() === therapistLat && 
                markerPosition.lng() === therapistLng) {
                
                // Close all info windows
                infoWindows.forEach(window => window.close());
                
                // Open this info window
                infoWindows[index].open(map, marker);
                
                // Pan to marker
                map.panTo(markerPosition);
                
                markerFound = true;
            }
        });
        
        if (!markerFound) {
            console.log("Marker not found for selected therapist");
        }
        
        // Show details panel
        showTherapistDetails(therapist);
    }
    
    // Show therapist details in the detail panel
    function showTherapistDetails(therapist) {
        console.log("Showing details for therapist:", therapist.name);
        
        if (!therapistDetails) {
            console.error("Therapist details element not found");
            return;
        }
        
        // Normalize therapist data
        const name = therapist.name || 'Unknown Therapist';
        const specialty = therapist.specialty || 'Therapist';
        const initials = therapist.initials || name.split(' ').slice(0, 2).map(part => part[0]).join('');
        const rating = therapist.rating || 4.0;
        const reviewCount = therapist.reviewCount || therapist.user_ratings_total || 0;
        const phone = therapist.phone || therapist.formatted_phone_number || 'Contact for details';
        const website = therapist.website || '#';
        const address = therapist.address || therapist.vicinity || therapist.formatted_address || 'Address not available';
        const distance = therapist.distance || 'Unknown';
        
        // Generate reviews HTML
        let reviewsHtml = '<p class="no-reviews">No reviews available.</p>';
        if (therapist.reviews && therapist.reviews.length > 0) {
            reviewsHtml = therapist.reviews.map(review => `
                <div class="therapist-review">
                    <div class="review-header">
                        <div class="review-author">${review.author_name || review.author || 'Anonymous'}</div>
                        <div class="review-date">${review.relative_time_description || review.date || 'Recent'}</div>
                    </div>
                    <div class="review-rating">
                        ${generateStars(review.rating || 4)}
                    </div>
                    <div class="review-text">${review.text || 'No comment provided.'}</div>
                </div>
            `).join('');
        }
        
        // Update details panel
        therapistDetails.innerHTML = `
            <div class="therapist-details-header">
                <div class="therapist-large-avatar">${initials}</div>
                <div class="therapist-header-info">
                    <h2 class="therapist-header-name">${name}</h2>
                    <div class="therapist-header-specialty">${specialty}</div>
                    <div class="therapist-rating">
                        ${generateStars(rating)}
                        <span>${rating} (${reviewCount})</span>
                    </div>
                </div>
                ${phone !== 'Contact for details' ? 
                  `<button class="therapist-contact-btn" onclick="window.open('tel:${phone.replace(/[^0-9]/g, '')}')">
                      <i class="fas fa-phone"></i> Contact
                  </button>` : 
                  `<button class="therapist-contact-btn" onclick="window.open('${website}', '_blank')">
                      <i class="fas fa-info-circle"></i> Info
                  </button>`
                }
            </div>
            
            <div class="therapist-full-details">
                <div class="therapist-detail-column">
                    <div class="therapist-detail-section">
                        <h4>Contact Information</h4>
                        <div class="therapist-detail-item">
                            <i class="fas fa-phone"></i>
                            <span>${phone}</span>
                        </div>
                        ${website && website !== '#' ? 
                          `<div class="therapist-detail-item">
                              <i class="fas fa-globe"></i>
                              <a href="${website}" target="_blank">Visit Website</a>
                          </div>` : ''
                        }
                    </div>
                    
                    <div class="therapist-detail-section">
                        <h4>Practice Information</h4>
                        <div class="therapist-detail-item">
                            <i class="fas fa-map-marker-alt"></i>
                            <span>${address}</span>
                        </div>
                        <div class="therapist-detail-item">
                            <i class="fas fa-route"></i>
                            <span>${distance} miles from your location</span>
                        </div>
                    </div>
                </div>
                
                <div class="therapist-detail-column">
                    <div class="therapist-detail-section">
                        <h4>Reviews</h4>
                        <div class="therapist-reviews">
                            ${reviewsHtml}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Show details panel
        therapistDetails.style.display = 'block';
        
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.className = 'close-details-btn';
        closeButton.innerHTML = '<i class="fas fa-times"></i>';
        therapistDetails.appendChild(closeButton);
        
        // Add event listener to close button
        closeButton.addEventListener('click', function() {
            therapistDetails.style.display = 'none';
        });
    }

    // Function to initialize map in index.html
    function initializeMainPageMap() {
        console.log("Initializing main page map");
        
        // Check if we're on the main page by looking for the therapistMap element
        const mainPageMapElement = document.getElementById('therapistMap');
        if (!mainPageMapElement) {
            console.log("Not on main page, skipping map initialization");
            return;
        }
        
        // Create a map instance for the main page
        try {
            // Default map center (USA)
            const defaultLocation = { lat: 37.0902, lng: -95.7129 };
            
            // Create the map
            console.log("Creating main page map");
            
            mainPageMap = new google.maps.Map(mainPageMapElement, {
                center: defaultLocation,
                zoom: 4,
                mapTypeControl: false,
                streetViewControl: false,
                fullscreenControl: true
            });
            
            console.log("Main page map created successfully");
            
            // Initialize main page variables (removed declaration since they're now global)
            mainPageUserMarker = null;
            mainPageTherapistMarkers = [];
            mainPageInfoWindows = [];
            mainPageUserLocation = null;
            
            // Initialize geocoder for main page
            mainPageGeocoder = new google.maps.Geocoder();
            
            // Initialize places service for main page
            mainPagePlacesService = new google.maps.places.PlacesService(mainPageMap);
            
            // Create bounds object
            mainPageBounds = new google.maps.LatLngBounds();
            
            // Set up location search with Places Autocomplete
            const mainPageLocationSearch = document.getElementById('therapistLocationSearch');
            if (mainPageLocationSearch) {
                const autocomplete = new google.maps.places.Autocomplete(mainPageLocationSearch, {
                    types: ['geocode']
                });
                
                autocomplete.addListener('place_changed', function() {
                    const place = autocomplete.getPlace();
                    if (place.geometry) {
                        // Update user location
                        mainPageUserLocation = {
                            latitude: place.geometry.location.lat(),
                            longitude: place.geometry.location.lng()
                        };
                        
                        // Update map view
                        updateMainPageUserLocation();
                    }
                });
            }
            
            // Set up event listener for the Find Therapists button
            const findTherapistsBtn = document.getElementById('findTherapistsBtn');
            if (findTherapistsBtn) {
                console.log("Find Therapists button found, adding click event listener");
                findTherapistsBtn.addEventListener('click', function() {
                    console.log("Find Therapists button clicked");
                    searchMainPageTherapists();
                });
            } else {
                console.error("Find Therapists button not found");
            }
            
            // Set up event listener for the Detect Location button
            const detectLocationBtn = document.getElementById('detectLocationBtn');
            if (detectLocationBtn) {
                detectLocationBtn.addEventListener('click', function() {
                    detectMainPageUserLocation();
                });
            }
            
            // Function to detect user's location on main page
            function detectMainPageUserLocation() {
                if (!navigator.geolocation) {
                    alert("Geolocation is not supported by your browser");
                    return;
                }
                
                // Show loading spinner in the button
                if (detectLocationBtn) {
                    detectLocationBtn.innerHTML = '<i class="fas fa-spinner location-spinner"></i>';
                    detectLocationBtn.disabled = true;
                }
                
                navigator.geolocation.getCurrentPosition(
                    // Success callback
                    function(position) {
                        // Reset button
                        if (detectLocationBtn) {
                            detectLocationBtn.innerHTML = '<i class="fas fa-crosshairs"></i>';
                            detectLocationBtn.disabled = false;
                        }
                        
                        // Store the location
                        mainPageUserLocation = {
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude
                        };
                        
                        // Update the map
                        updateMainPageUserLocation();
                        
                        // Try to get an address for the detected location
                        reverseGeocodeMainPage(position.coords.latitude, position.coords.longitude);
                        
                        // Automatically search for therapists near this location
                        fetchMainPageTherapists(
                            mainPageUserLocation.latitude, 
                            mainPageUserLocation.longitude, 
                            document.getElementById('therapistSpecialtyFilter')?.value || ''
                        );
                    },
                    // Error callback
                    function(error) {
                        // Reset button
                        if (detectLocationBtn) {
                            detectLocationBtn.innerHTML = '<i class="fas fa-crosshairs"></i>';
                            detectLocationBtn.disabled = false;
                        }
                        
                        let errorMessage = "Unable to retrieve your location. ";
                        
                        switch(error.code) {
                            case error.PERMISSION_DENIED:
                                errorMessage += "You denied the request for geolocation.";
                                break;
                            case error.POSITION_UNAVAILABLE:
                                errorMessage += "Location information is unavailable.";
                                break;
                            case error.TIMEOUT:
                                errorMessage += "The request to get your location timed out.";
                                break;
                            case error.UNKNOWN_ERROR:
                                errorMessage += "An unknown error occurred.";
                                break;
                        }
                        
                        alert(errorMessage);
                    },
                    // Options
                    {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0
                    }
                );
            }
            
            // Function to update user location on main page map
            function updateMainPageUserLocation() {
                if (!mainPageMap || !mainPageUserLocation) return;
                
                const position = new google.maps.LatLng(mainPageUserLocation.latitude, mainPageUserLocation.longitude);
                
                // Create or update user marker
                if (mainPageUserMarker) {
                    mainPageUserMarker.setPosition(position);
                } else {
                    // Create custom user marker
                    mainPageUserMarker = new google.maps.Marker({
                        position: position,
                        map: mainPageMap,
                        icon: {
                            path: google.maps.SymbolPath.CIRCLE,
                            scale: 10,
                            fillColor: '#5B6EF5',
                            fillOpacity: 1,
                            strokeColor: '#ffffff',
                            strokeWeight: 2
                        },
                        title: 'Your Location',
                        zIndex: 1000
                    });
                    
                    // Add info window
                    const infoWindow = new google.maps.InfoWindow({
                        content: '<div class="map-popup"><h3>Your Location</h3></div>'
                    });
                    
                    mainPageUserMarker.addListener('click', function() {
                        infoWindow.open(mainPageMap, mainPageUserMarker);
                    });
                }
                
                // Center map on user location
                mainPageMap.setCenter(position);
                mainPageMap.setZoom(12);
            }
            
            // Function to reverse geocode coordinates on main page
            function reverseGeocodeMainPage(lat, lng) {
                if (!mainPageGeocoder) return;
                
                const latlng = { lat: lat, lng: lng };
                
                mainPageGeocoder.geocode({ 'location': latlng }, function(results, status) {
                    if (status === 'OK') {
                        if (results[0] && mainPageLocationSearch) {
                            // Update the search input with the formatted address
                            mainPageLocationSearch.value = results[0].formatted_address;
                        }
                    }
                });
            }
            
            // Function to search for therapists on main page
            function searchMainPageTherapists() {
                console.log("searchMainPageTherapists called");
                
                // Get location and specialty
                const locationInput = document.getElementById('therapistLocationSearch');
                console.log("Location input element:", locationInput);
                const specialtySelect = document.getElementById('therapistSpecialtyFilter');
                console.log("Specialty select element:", specialtySelect);
                
                if (!locationInput || !locationInput.value.trim()) {
                    console.log("No location provided");
                    alert('Please enter a location to search for therapists');
                    return;
                }
                
                const location = locationInput.value.trim();
                console.log("Location:", location);
                const specialty = specialtySelect ? specialtySelect.value : '';
                console.log("Specialty:", specialty);
                
                // If we already have user location coordinates, use them directly
                if (mainPageUserLocation) {
                    console.log("Using existing user location:", mainPageUserLocation);
                    fetchMainPageTherapists(
                        mainPageUserLocation.latitude, 
                        mainPageUserLocation.longitude, 
                        specialty
                    );
                } else {
                    console.log("No existing user location, geocoding address");
                    // Otherwise, geocode the location string
                    if (!mainPageGeocoder) {
                        console.error("Geocoder not initialized");
                        return;
                    }
                    
                    mainPageGeocoder.geocode({ address: location }, function(results, status) {
                        console.log("Geocode results:", status, results);
                        if (status === 'OK' && results[0]) {
                            const position = results[0].geometry.location;
                            
                            // Store the location
                            mainPageUserLocation = {
                                latitude: position.lat(),
                                longitude: position.lng()
                            };
                            console.log("Geocoded location:", mainPageUserLocation);
                            
                            // Update map
                            updateMainPageUserLocation();
                            
                            // Fetch therapists
                            fetchMainPageTherapists(position.lat(), position.lng(), specialty);
                        } else {
                            console.error('Geocode was not successful for the following reason:', status);
                            alert('Could not find the location. Please try a different search term.');
                        }
                    });
                }
            }
            
            // Function to fetch therapists for main page
            function fetchMainPageTherapists(lat, lng, specialty) {
                console.log("fetchMainPageTherapists called with:", lat, lng, specialty);
                
                // Show loading state in therapist list
                const therapistList = document.getElementById('therapistList');
                console.log("Therapist list element:", therapistList);
                
                if (therapistList) {
                    therapistList.innerHTML = `
                        <div class="therapist-list-placeholder">
                            <i class="fas fa-spinner fa-spin"></i>
                            <p>Searching for therapists...</p>
                        </div>
                    `;
                }
                
                // Prepare query parameters
                // Handle specialty mapping - ensure it conforms to what the API expects
                let specialtyParam = specialty || '';
                
                // Map specialty values to match the backend API expectations
                if (specialtyParam && specialtyParam !== 'all' && specialtyParam !== '') {
                    console.log(`Mapping specialty "${specialtyParam}" to API format`);
                    // This mapping should match what's in app.py
                    const specialtyMap = {
                        'anxiety': 'anxiety',
                        'depression': 'depression',
                        'trauma': 'trauma',
                        'couples': 'relationship',
                        'addiction': 'addiction'
                    };
                    specialtyParam = specialtyMap[specialtyParam] || specialtyParam;
                    console.log(`Mapped to: "${specialtyParam}"`);
                }
                
                const searchParams = new URLSearchParams({
                    lat: lat,
                    lng: lng,
                    specialty: specialtyParam
                });
                console.log("Search params:", searchParams.toString());
                
                // Fetch therapist data from our API
                const apiUrl = `/api/nearby-therapists?${searchParams.toString()}`;
                console.log("Fetching from API URL:", apiUrl);
                
                fetch(apiUrl)
                    .then(response => {
                        console.log("API response status:", response.status);
                        if (!response.ok) {
                            throw new Error(`Failed to fetch therapists: ${response.status} ${response.statusText}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log("API response data:", data);
                        if (data && data.results && data.results.length > 0) {
                            // Process the data
                            const therapists = processMainPageTherapistResults(data.results, lat, lng);
                            console.log("Processed therapists:", therapists);
                            
                            // Display the therapists
                            displayMainPageTherapists(therapists);
                        } else {
                            console.log("No therapist results found");
                            // No results
                            if (therapistList) {
                                therapistList.innerHTML = `
                                    <div class="therapist-list-placeholder">
                                        <i class="fas fa-user-md"></i>
                                        <p>No therapists found in this area. Try expanding your search or changing the specialty.</p>
                                    </div>
                                `;
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching therapists:', error);
                        if (therapistList) {
                            therapistList.innerHTML = `
                                <div class="therapist-list-placeholder">
                                    <i class="fas fa-exclamation-triangle"></i>
                                    <p>There was an error finding therapists. Please try again later.</p>
                                </div>
                            `;
                        }
                    });
            }
            
            // Process Google Places API results for main page
            function processMainPageTherapistResults(results, userLat, userLng) {
                return results.map(place => {
                    const location = place.geometry?.location;
                    if (!location) return null;
                    
                    // Calculate distance
                    const distance = calculateDistance(
                        userLat, userLng, 
                        typeof location.lat === 'function' ? location.lat() : location.lat, 
                        typeof location.lng === 'function' ? location.lng() : location.lng
                    );
                    
                    // Extract specialty from types or name
                    let specialty = 'Therapy';
                    const lowerName = place.name.toLowerCase();
                    
                    if (lowerName.includes('psychologist') || lowerName.includes('psychology')) {
                        specialty = 'Psychology';
                    } else if (lowerName.includes('psychiatrist') || lowerName.includes('psychiatry')) {
                        specialty = 'Psychiatry';
                    } else if (lowerName.includes('marriage') || lowerName.includes('couple')) {
                        specialty = 'Couples Therapy';
                    } else if (lowerName.includes('child') || lowerName.includes('pediatric')) {
                        specialty = 'Child Therapy';
                    } else if (lowerName.includes('trauma')) {
                        specialty = 'Trauma & PTSD';
                    } else if (lowerName.includes('depress')) {
                        specialty = 'Depression';
                    } else if (lowerName.includes('anxiety')) {
                        specialty = 'Anxiety';
                    }
                    
                    // Generate initials from name
                    const nameParts = place.name.split(' ');
                    let initials = '';
                    for (let i = 0; i < Math.min(nameParts.length, 2); i++) {
                        if (nameParts[i].length > 0) {
                            initials += nameParts[i][0].toUpperCase();
                        }
                    }
                    if (initials.length === 0) initials = 'T';
                    
                    // Process reviews if available
                    const reviews = place.reviews || [];
                    
                    // Create our standardized therapist object
                    return {
                        id: place.place_id || place.id,
                        name: place.name,
                        specialty: specialty,
                        latitude: typeof location.lat === 'function' ? location.lat() : location.lat,
                        longitude: typeof location.lng === 'function' ? location.lng() : location.lng,
                        distance: distance,
                        rating: place.rating || (3.5 + Math.random() * 1.5).toFixed(1),
                        reviewCount: place.user_ratings_total || reviews.length,
                        phone: place.formatted_phone_number || place.phone || 'Contact for details',
                        website: place.website || '#',
                        address: place.vicinity || place.formatted_address || place.address || 'Address not available',
                        initials: initials,
                        reviews: reviews.map(review => ({
                            author: review.author_name || 'Anonymous',
                            date: review.relative_time_description || 'Recent',
                            rating: review.rating || 4,
                            text: review.text || 'No comment provided.'
                        }))
                    };
                }).filter(Boolean);
            }
            
            // Display therapists on main page
            function displayMainPageTherapists(therapists) {
                console.log("displayMainPageTherapists called with", therapists.length, "therapists");
                console.log("Therapist data sample:", JSON.stringify(therapists[0], null, 2));
                // Clear previous markers
                mainPageTherapistMarkers.forEach(marker => marker.setMap(null));
                mainPageTherapistMarkers = [];
                
                // Close all info windows
                mainPageInfoWindows.forEach(infoWindow => infoWindow.close());
                mainPageInfoWindows = [];
                
                // Clear therapist list
                const therapistList = document.getElementById('therapistList');
                if (!therapistList) {
                    console.error("Therapist list element not found!");
                    return;
                }
                
                therapistList.innerHTML = '';
                
                // Hide details panel if shown
                const therapistDetails = document.getElementById('therapistDetails');
                if (therapistDetails) {
                    therapistDetails.style.display = 'none';
                }
                
                if (therapists.length === 0) {
                    therapistList.innerHTML = `
                        <div class="therapist-list-placeholder">
                            <i class="fas fa-user-md"></i>
                            <p>No therapists found in this area. Try expanding your search.</p>
                        </div>
                    `;
                    return;
                }
                
                // Reset bounds
                mainPageBounds = new google.maps.LatLngBounds();
                
                // Add user location to bounds
                if (mainPageUserLocation) {
                    mainPageBounds.extend(new google.maps.LatLng(mainPageUserLocation.latitude, mainPageUserLocation.longitude));
                }
                
                // Add therapist markers and list items
                therapists.forEach((therapist, index) => {
                    try {
                        // Extract location data with better error handling
                        const location = therapist.geometry?.location || { lat: therapist.latitude, lng: therapist.longitude };
                        const lat = typeof location.lat === 'function' ? location.lat() : location.lat;
                        const lng = typeof location.lng === 'function' ? location.lng() : location.lng;
                        
                        if (!lat || !lng) {
                            console.error(`Invalid coordinates for therapist ${index}:`, therapist);
                            return;
                        }
                        
                        console.log(`Creating marker for therapist ${index} at (${lat}, ${lng})`);
                        
                        // Create marker position
                        const position = new google.maps.LatLng(lat, lng);
                        
                        // Add marker to map
                        const marker = new google.maps.Marker({
                            position: position,
                            map: mainPageMap,
                            title: therapist.name,
                            icon: {
                                path: google.maps.SymbolPath.CIRCLE,
                                scale: 8,
                                fillColor: '#ef4444',
                                fillOpacity: 1,
                                strokeColor: '#ffffff',
                                strokeWeight: 2
                            }
                        });
                        
                        // Create info window content
                        const infoWindowContent = `
                            <div class="map-popup">
                                <h3>${therapist.name}</h3>
                                <p>${therapist.specialty}</p>
                                <p><i class="fas fa-map-marker-alt"></i> ${therapist.distance} miles away</p>
                                <p>${therapist.address}</p>
                                <p>${therapist.phone}</p>
                                ${therapist.website && therapist.website !== '#' ? 
                                  `<p><a href="${therapist.website}" target="_blank">Visit Website</a></p>` : ''}
                            </div>
                        `;
                        
                        // Create info window
                        const infoWindow = new google.maps.InfoWindow({
                            content: infoWindowContent
                        });
                        
                        mainPageInfoWindows.push(infoWindow);
                        
                        // Add click event to marker
                        marker.addListener('click', function() {
                            // Close all open info windows
                            mainPageInfoWindows.forEach(window => window.close());
                            
                            // Open this info window
                            infoWindow.open(mainPageMap, marker);
                            
                            // Show therapist details
                            showMainPageTherapistDetails(therapist);
                        });
                        
                        // Add marker to array
                        mainPageTherapistMarkers.push(marker);
                        
                        // Add to bounds
                        mainPageBounds.extend(position);
                        
                        // Create list item
                        const therapistItem = document.createElement('div');
                        therapistItem.className = 'therapist-item';
                        therapistItem.dataset.id = therapist.place_id || therapist.id;
                        
                        const starRating = generateStars(therapist.rating);
                        
                        // Generate initials from name
                        const nameParts = therapist.name.split(' ');
                        let initials = '';
                        for (let i = 0; i < Math.min(nameParts.length, 2); i++) {
                            if (nameParts[i].length > 0) {
                                initials += nameParts[i][0].toUpperCase();
                            }
                        }
                        if (initials.length === 0) initials = 'T';
                        
                        therapistItem.innerHTML = `
                            <div class="therapist-item-header">
                                <div class="therapist-avatar">${initials}</div>
                                <div class="therapist-info">
                                    <h3 class="therapist-name">${therapist.name}</h3>
                                    <div class="therapist-specialty">${therapist.specialty || 'Therapist'}</div>
                                    <div class="therapist-distance">${therapist.distance} miles away</div>
                                </div>
                            </div>
                        `;
                        
                        // Add click event to list item
                        therapistItem.addEventListener('click', function() {
                            // Show therapist details
                            showMainPageTherapistDetails(therapist);
                            
                            // Find and open the marker's info window
                            for (let i = 0; i < mainPageTherapistMarkers.length; i++) {
                                const markerPosition = mainPageTherapistMarkers[i].getPosition();
                                if (markerPosition.lat() === lat && 
                                    markerPosition.lng() === lng) {
                                    
                                    // Close all info windows
                                    mainPageInfoWindows.forEach(window => window.close());
                                    
                                    // Open this info window
                                    mainPageInfoWindows[i].open(mainPageMap, mainPageTherapistMarkers[i]);
                                    
                                    // Pan to marker
                                    mainPageMap.panTo(markerPosition);
                                    break;
                                }
                            }
                        });
                        
                        // Add to list
                        therapistList.appendChild(therapistItem);
                        console.log(`Added therapist ${index} to list`);
                    } catch (error) {
                        console.error(`Error creating therapist ${index}:`, error, therapist);
                    }
                });
                
                // Fit map to bounds
                if (!mainPageBounds.isEmpty()) {
                    console.log("Fitting map to bounds");
                    mainPageMap.fitBounds(mainPageBounds, 50); // 50px padding
                } else {
                    console.warn("Bounds is empty, cannot fit map");
                }
            }
            
            // Show therapist details on main page
            function showMainPageTherapistDetails(therapist) {
                const therapistDetails = document.getElementById('therapistDetails');
                if (!therapistDetails) return;
                
                // Update therapist list selection
                const items = document.querySelectorAll('.therapist-item');
                items.forEach(item => {
                    item.classList.remove('active');
                    if (item.dataset.id === therapist.id) {
                        item.classList.add('active');
                        item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                });
                
                // Generate reviews HTML
                let reviewsHtml = '<p class="no-reviews">No reviews available.</p>';
                if (therapist.reviews && therapist.reviews.length > 0) {
                    reviewsHtml = therapist.reviews.map(review => `
                        <div class="therapist-review">
                            <div class="review-header">
                                <div class="review-author">${review.author}</div>
                                <div class="review-date">${review.date}</div>
                            </div>
                            <div class="review-rating">
                                ${generateStars(review.rating)}
                            </div>
                            <div class="review-text">${review.text}</div>
                        </div>
                    `).join('');
                }
                
                // Update details panel
                therapistDetails.innerHTML = `
                    <div class="therapist-details-header">
                        <div class="therapist-large-avatar">${therapist.initials}</div>
                        <div class="therapist-header-info">
                            <h2 class="therapist-header-name">${therapist.name}</h2>
                            <div class="therapist-header-specialty">${therapist.specialty}</div>
                            <div class="therapist-rating">
                                ${generateStars(therapist.rating)}
                                <span>${therapist.rating} (${therapist.reviewCount})</span>
                            </div>
                        </div>
                        ${therapist.phone !== 'Contact for details' ? 
                          `<button class="therapist-contact-btn" onclick="window.open('tel:${therapist.phone.replace(/[^0-9]/g, '')}')">
                              <i class="fas fa-phone"></i> Contact
                          </button>` : 
                          `<button class="therapist-contact-btn" onclick="window.open('${therapist.website}', '_blank')">
                              <i class="fas fa-info-circle"></i> Info
                          </button>`
                        }
                    </div>
                    
                    <div class="therapist-full-details">
                        <div class="therapist-detail-column">
                            <div class="therapist-detail-section">
                                <h4>Contact Information</h4>
                                <div class="therapist-detail-item">
                                    <i class="fas fa-phone"></i>
                                    <span>${therapist.phone}</span>
                                </div>
                                ${therapist.website && therapist.website !== '#' ? 
                                  `<div class="therapist-detail-item">
                                      <i class="fas fa-globe"></i>
                                      <a href="${therapist.website}" target="_blank">Visit Website</a>
                                  </div>` : ''
                                }
                            </div>
                            
                            <div class="therapist-detail-section">
                                <h4>Practice Information</h4>
                                <div class="therapist-detail-item">
                                    <i class="fas fa-map-marker-alt"></i>
                                    <span>${therapist.address}</span>
                                </div>
                                <div class="therapist-detail-item">
                                    <i class="fas fa-route"></i>
                                    <span>${therapist.distance} miles from your location</span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="therapist-detail-column">
                            <div class="therapist-detail-section">
                                <h4>Reviews</h4>
                                <div class="therapist-reviews">
                                    ${reviewsHtml}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Show details panel
                therapistDetails.style.display = 'block';
                
                // Add close button
                const closeButton = document.createElement('button');
                closeButton.className = 'close-details-btn';
                closeButton.innerHTML = '<i class="fas fa-times"></i>';
                therapistDetails.appendChild(closeButton);
                
                // Add event listener to close button
                closeButton.addEventListener('click', function() {
                    therapistDetails.style.display = 'none';
                });
            }
        } catch (error) {
            console.error("Error initializing main page map:", error);
        }
    }

    // Run initialization when page loads
    if (window.location.pathname === '/' || window.location.pathname === '/index') {
        console.log("Loading main page map");
        
        // Add tab change handler to reinitialize map when switching to therapist tab
        const therapistsTab = document.querySelector('[data-tab="therapists"]');
        if (therapistsTab) {
            console.log("Found therapists tab, adding click handler");
            therapistsTab.addEventListener('click', function() {
                console.log("Therapists tab clicked");
                
                // Check if Google Maps API is loaded
                if (typeof google !== 'undefined' && google.maps) {
                    // Ensure map element exists
                    const mapElement = document.getElementById('therapistMap');
                    if (!mapElement) {
                        console.error("Map element not found");
                        return;
                    }
                    
                    // Check if map is already initialized
                    if (!mainPageMap || !window.mapInitialized) {
                        console.log("Map not initialized, initializing now");
                        if (window.initMap) {
                            window.initMap();
                        } else {
                            console.error("initMap function not available");
                        }
                    } else {
                        console.log("Map already initialized, triggering resize");
                        // Trigger resize event to fix rendering issues
                        google.maps.event.trigger(mainPageMap, 'resize');
                        
                        // If we have bounds, fit to them
                        if (mainPageBounds && !mainPageBounds.isEmpty()) {
                            mainPageMap.fitBounds(mainPageBounds);
                        } else if (mainPageUserLocation) {
                            // Center on user location if available
                            mainPageMap.setCenter(new google.maps.LatLng(
                                mainPageUserLocation.latitude,
                                mainPageUserLocation.longitude
                            ));
                        }
                    }
                } else {
                    console.error("Google Maps API not loaded");
                }
            });
        }
        
        // Wait for Google Maps to fully load
        if (typeof google !== 'undefined' && google.maps) {
            console.log("Google Maps already loaded, initializing map");
            initializeMainPageMap();
        } else {
            // If Google Maps isn't loaded yet, wait for it
            console.log("Waiting for Google Maps to load");
            window.addEventListener('load', function() {
                setTimeout(function() {
                    if (typeof google !== 'undefined' && google.maps) {
                        console.log("Google Maps loaded, initializing map");
                        initializeMainPageMap();
                    } else {
                        console.error("Google Maps API failed to load");
                    }
                }, 1000); // Give extra time for the API to initialize
            });
        }
    } else if (window.location.pathname === '/nearby_therapists' || window.location.pathname === '/find-therapists') {
        console.log("On dedicated therapist page");
        
        // Add window resize handler
        window.addEventListener('resize', function() {
            if (map && typeof google !== 'undefined' && google.maps) {
                console.log("Window resized, triggering map resize");
                google.maps.event.trigger(map, 'resize');
                
                if (bounds && !bounds.isEmpty()) {
                    map.fitBounds(bounds);
                } else if (userLocation) {
                    map.setCenter(new google.maps.LatLng(userLocation.latitude, userLocation.longitude));
                }
            }
        });
        
        // Add event listener to handle window visibility changes (e.g., tab switching)
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden && map && typeof google !== 'undefined' && google.maps) {
                console.log("Page visible again, triggering map resize");
                setTimeout(function() {
                    google.maps.event.trigger(map, 'resize');
                    
                    if (bounds && !bounds.isEmpty()) {
                        map.fitBounds(bounds);
                    } else if (userLocation) {
                        map.setCenter(new google.maps.LatLng(userLocation.latitude, userLocation.longitude));
                    }
                }, 500);
            }
        });
    }

    // Direct functions called from the index.html page
    window.directTherapistSearch = function() {
        console.log("Direct therapist search called from index.html");
        searchTherapists();
    };

    window.directDetectLocation = function() {
        console.log("Direct detect location called from index.html");
        detectUserLocation();
    };

    // Create a marker for a therapist
    function createTherapistMarker(position, therapist, index) {
        if (!map) {
            console.error("Map not initialized when attempting to add marker");
            return null;
        }
        
        // Create marker
        const marker = new google.maps.Marker({
            position: position,
            map: map,
            title: therapist.name,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 8,
                fillColor: '#5B6EF5',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 2
            },
            zIndex: 1
        });
        
        // Extract ID
        const therapistId = therapist.place_id || therapist.id || `t-${index}`;
        
        // Create info window content
        const infoWindowContent = `
            <div class="map-popup">
                <h3>${therapist.name}</h3>
                <p>${therapist.specialty || 'Therapist'}</p>
                <p><i class="fas fa-map-marker-alt"></i> ${
                    therapist.distance ? 
                    `${therapist.distance} miles away` : 
                    'Distance unavailable'
                }</p>
                <button class="popup-details-btn" data-id="${therapistId}">View Details</button>
            </div>
        `;
        
        // Create info window
        const infoWindow = new google.maps.InfoWindow({
            content: infoWindowContent
        });
        
        infoWindows.push(infoWindow);
        
        // Add click event to marker
        marker.addListener('click', function() {
            // Close all open info windows
            infoWindows.forEach(window => window.close());
            
            // Open this info window
            infoWindow.open(map, marker);
            
            // Add click event to the "View Details" button in the info window
            google.maps.event.addListener(infoWindow, 'domready', function() {
                const detailsBtn = document.querySelector(`.popup-details-btn[data-id="${therapistId}"]`);
                if (detailsBtn) {
                    detailsBtn.addEventListener('click', function() {
                        selectTherapist(therapist);
                    });
                }
            });
        });
        
        // Add marker to array
        therapistMarkers.push(marker);
        
        return marker;
    }
}); 