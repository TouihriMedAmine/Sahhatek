// HealthcareMap class - updated for location consent
class HealthcareMap {
    constructor(mapId) {
        this.mapId = mapId;
        this.map = null;
        this.userLat = null;
        this.userLon = null;
        this.userMarker = null;
        this.places = [];
        this.routingControl = null;
        this.locationAsked = false;
    }

    init(defaultLat = 36.8883559, defaultLon = 10.183846) {
        // Always use default coordinates initially
        this.userLat = defaultLat;
        this.userLon = defaultLon;
        
        // Initialize map with default location
        this.map = L.map(this.mapId).setView([this.userLat, this.userLon], 13);
        
        // Add tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);
        
        console.log(`🗺️ Map initialized at default location: ${this.userLat}, ${this.userLon}`);
        
        // Add user marker at default location
        this.addUserMarker(this.userLat, this.userLon);
        
        // Add click handler to request location if needed
        this.addLocationRequestButton();
    }

    addUserMarker(lat, lon) {
        // Remove existing marker
        if (this.userMarker) {
            this.map.removeLayer(this.userMarker);
        }
        
        // Add new marker
        this.userMarker = L.marker([lat, lon])
            .addTo(this.map)
            .bindPopup('<b>Your Location</b><br>Default or approximate location')
            .openPopup();
    }

    addLocationRequestButton() {
        // Create location request button
        const locationButton = L.control({position: 'topright'});
        
        locationButton.onAdd = () => {
            const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            const button = L.DomUtil.create('a', '', div);
            button.innerHTML = '<i class="fas fa-location-crosshairs"></i>';
            button.title = 'Request your precise location';
            button.style.cssText = 'width: 30px; height: 30px; line-height: 30px; text-align: center; background: white; cursor: pointer;';
            
            button.onclick = async (e) => {
                L.DomEvent.stopPropagation(e);
                await this.requestUserLocation();
            };
            
            return div;
        };
        
        locationButton.addTo(this.map);
    }

    async requestUserLocation() {
        if (this.locationAsked) {
            console.log("📍 Location already asked for this session");
            return;
        }
        
        if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser.");
            return;
        }
        
        this.locationAsked = true;
        
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                });
            });
            
            const userLat = position.coords.latitude;
            const userLon = position.coords.longitude;
            
            // Update global user location
            window.userLocation = { latitude: userLat, longitude: userLon };
            
            // Update map
            this.userLat = userLat;
            this.userLon = userLon;
            this.map.setView([userLat, userLon], 15);
            
            // Update marker
            this.addUserMarker(userLat, userLon);
            
            // Update places with new user location
            if (this.places.length > 0) {
                this.showRouteToNearest();
            }
            
            console.log(`📍 User location updated: ${userLat}, ${userLon}`);
            
        } catch (error) {
            console.warn("📍 Location request failed:", error.message);
            alert("Unable to get your location. Please check your browser permissions.");
        }
    }

    addPlaces(places) {
        this.places = places;
        
        // Add markers for each place
        places.forEach((place, index) => {
            const marker = L.marker([place.latitude, place.longitude])
                .addTo(this.map)
                .bindPopup(`
                    <b>${place.name}</b><br>
                    ${place.type}<br>
                    Distance: ${place.distance} km<br>
                    ${place.address ? `Address: ${place.address}` : ''}
                `);
            
            // Add click handler for routing
            marker.on('click', () => {
                this.showRoute(place.latitude, place.longitude, place.name);
            });
        });
        
        // If user has precise location, show route to nearest
        if (window.userLocation && window.userLocation.latitude && window.userLocation.longitude) {
            this.showRouteToNearest();
        }
    }

    showRoute(destLat, destLon, destName) {
        // Remove existing routing control
        if (this.routingControl) {
            this.map.removeControl(this.routingControl);
        }
        
        // Add new routing control
        this.routingControl = L.Routing.control({
            waypoints: [
                L.latLng(this.userLat, this.userLon),
                L.latLng(destLat, destLon)
            ],
            routeWhileDragging: false,
            showAlternatives: false,
            lineOptions: {
                styles: [{color: '#d80027', weight: 5}]
            },
            createMarker: function(i, wp) {
                if (i === 0) {
                    return L.marker(wp.latLng, {
                        icon: L.divIcon({
                            html: '<div style="background: #d80027; width: 20px; height: 20px; border-radius: 50%;"></div>',
                            iconSize: [20, 20]
                        })
                    }).bindPopup("Your Location");
                } else {
                    return L.marker(wp.latLng, {
                        icon: L.divIcon({
                            html: '<div style="background: #0066cc; width: 20px; height: 20px; border-radius: 50%;"></div>',
                            iconSize: [20, 20]
                        })
                    }).bindPopup(`<b>${destName}</b>`);
                }
            }
        }).addTo(this.map);
    }

    showRouteToNearest() {
        if (this.places.length === 0) return;
        
        // Find nearest place
        const nearest = this.places.reduce((prev, current) => {
            return prev.distance < current.distance ? prev : current;
        });
        
        this.showRoute(nearest.latitude, nearest.longitude, nearest.name);
    }
}

// Global function to show route from message list
window.showRouteFromList = function(latitude, longitude, name) {
    if (window.currentMapInstance) {
        window.currentMapInstance.showRoute(latitude, longitude, name);
    }
};