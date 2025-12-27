// static/js/map.js
// Map component for displaying healthcare facility recommendations

class HealthcareMap {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.map = null;
    this.markers = [];
    this.userMarker = null;
    this.userLat = null;
    this.userLon = null;
    this.routingControl = null;
    this.simpleRouteLine = null;
    this.options = {
      defaultZoom: 13,
      ...options
    };
  }

  init(lat, lon) {
    if (!lat || !lon) {
      console.error('Latitude and longitude are required');
      return;
    }

    // Store user location for routing
    this.userLat = lat;
    this.userLon = lon;

    // Initialize map
    this.map = L.map(this.containerId).setView([lat, lon], this.options.defaultZoom);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(this.map);

    // Add user location marker
    this.addUserMarker(lat, lon);
  }

  addUserMarker(lat, lon) {
    if (this.userMarker) {
      this.map.removeLayer(this.userMarker);
    }

    // Custom icon for user location
    const userIcon = L.divIcon({
      className: 'user-location-marker',
      html: '<div style="background-color: #3b82f6; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });

    this.userMarker = L.marker([lat, lon], { icon: userIcon })
      .addTo(this.map)
      .bindPopup('Your Location')
      .openPopup();
  }

  addPlace(place) {
    if (!this.map) {
      console.error('Map not initialized');
      return;
    }

    const { name, latitude, longitude, type, distance, address } = place;

    // Choose icon based on type
    const iconColor = this.getIconColor(type);
    const icon = L.divIcon({
      className: 'healthcare-marker',
      html: `<div style="background-color: ${iconColor}; width: 24px; height: 24px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); cursor: pointer;">
               <div style="transform: rotate(45deg); color: white; font-size: 12px; text-align: center; line-height: 20px;">${this.getTypeIcon(type)}</div>
             </div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 24]
    });

    const marker = L.marker([latitude, longitude], { icon })
      .addTo(this.map)
      .bindPopup(`
        <div style="min-width: 200px;">
          <h3 style="margin: 0 0 8px 0; font-weight: bold; color: #1f2937;">${name}</h3>
          <p style="margin: 4px 0; color: #6b7280; font-size: 14px;">
            <strong>Type:</strong> ${type}<br>
            <strong>Distance:</strong> ${distance} km<br>
            ${address ? `<strong>Address:</strong> ${address}` : ''}
          </p>
          ${this.userLat && this.userLon ? `
            <button onclick="window.showRouteToFacility(${latitude}, ${longitude}, '${name.replace(/'/g, "\\'")}')" 
                    style="margin-top: 8px; padding: 6px 12px; background-color: #8b5cf6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; width: 100%;">
              🗺️ Show Route
            </button>
          ` : ''}
        </div>
      `);

    // Add click handler to show route
    marker.on('click', () => {
      if (this.userLat && this.userLon) {
        this.showRoute(latitude, longitude, name);
      }
    });

    // Store place data in marker for reference
    marker.placeData = place;

    this.markers.push(marker);
    return marker;
  }

  addPlaces(places) {
    if (!places || places.length === 0) return;

    const bounds = [];
    
    // Add user location to bounds if exists
    if (this.userMarker) {
      bounds.push(this.userMarker.getLatLng());
    }

    places.forEach(place => {
      const marker = this.addPlace(place);
      if (marker) {
        bounds.push(marker.getLatLng());
      }
    });

    // Fit map to show all markers
    if (bounds.length > 0) {
      this.map.fitBounds(bounds, { padding: [50, 50] });
    }
  }

  getIconColor(type) {
    const colors = {
      'hospital': '#ef4444',      // red
      'clinic': '#f59e0b',         // amber
      'pharmacy': '#10b981',      // green
      'doctors': '#3b82f6',       // blue
      'default': '#8b5cf6'        // purple
    };
    return colors[type.toLowerCase()] || colors.default;
  }

  getTypeIcon(type) {
    const icons = {
      'hospital': '🏥',
      'clinic': '🏥',
      'pharmacy': '💊',
      'doctors': '👨‍⚕️',
      'default': '📍'
    };
    return icons[type.toLowerCase()] || icons.default;
  }

  showRoute(destLat, destLon, destinationName) {
    if (!this.userLat || !this.userLon) {
      console.warn('User location not available for routing');
      alert('Your location is not available. Please share your location first.');
      return;
    }

    console.log('Showing route from', this.userLat, this.userLon, 'to', destLat, destLon);

    // Remove existing route if any
    this.clearRoute();

    // Check if L.Routing is available
    if (typeof L.Routing === 'undefined') {
      console.error('Leaflet Routing Machine not loaded');
      // Fallback: draw a simple polyline
      this.showSimpleRoute(destLat, destLon, destinationName);
      return;
    }

    try {
      // Create routing control with OSRM (free routing service)
      this.routingControl = L.Routing.control({
        router: L.Routing.osrmv1({
          serviceUrl: 'https://router.project-osrm.org/route/v1',
          profile: 'driving'
        }),
        waypoints: [
          L.latLng(this.userLat, this.userLon),
          L.latLng(destLat, destLon)
        ],
        routeWhileDragging: false,
        addWaypoints: false,
        draggableWaypoints: false,
        fitSelectedRoutes: true,
        showAlternatives: false,
        show: false, // Hide the default routing instructions panel
        lineOptions: {
          styles: [
            {
              color: '#8b5cf6',
              opacity: 0.8,
              weight: 5
            }
          ]
        },
        createMarker: (i, waypoint) => {
          if (i === 0) {
            // User location marker - return null to use existing marker
            return null;
          } else {
            // Destination marker
            return L.marker(waypoint.latLng, {
              icon: L.divIcon({
                className: 'destination-marker',
                html: '<div style="background-color: #ef4444; width: 24px; height: 24px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
              })
            }).bindPopup(destinationName || 'Destination');
          }
        }
      }).addTo(this.map);

      // Handle route calculation
      this.routingControl.on('routesfound', (e) => {
        console.log('Route found:', e);
        const routes = e.routes;
        if (routes && routes.length > 0) {
          const route = routes[0];
          const distance = (route.summary.totalDistance / 1000).toFixed(2); // Convert to km
          const time = Math.round(route.summary.totalTime / 60); // Convert to minutes

          // Show route info in a custom popup
          const routeInfo = `
            <div style="padding: 8px; min-width: 200px;">
              <strong style="color: #1f2937;">Route to ${this.escapeHtml(destinationName || 'Destination')}</strong><br>
              <span style="color: #6b7280; font-size: 14px;">
                Distance: ${distance} km<br>
                Estimated time: ${time} minutes
              </span>
            </div>
          `;

          // Create a popup at the destination
          L.popup({ maxWidth: 250 })
            .setLatLng([destLat, destLon])
            .setContent(routeInfo)
            .openOn(this.map);
        }
      });

      // Handle errors
      this.routingControl.on('routingerror', (e) => {
        console.error('Routing error:', e);
        // Fallback to simple route
        this.showSimpleRoute(destLat, destLon, destinationName);
      });

      // Fit map to show the route
      this.map.fitBounds([
        [this.userLat, this.userLon],
        [destLat, destLon]
      ], { padding: [50, 50] });
    } catch (error) {
      console.error('Error creating routing control:', error);
      // Fallback to simple route
      this.showSimpleRoute(destLat, destLon, destinationName);
    }
  }

  showSimpleRoute(destLat, destLon, destinationName) {
    // Fallback: draw a simple polyline if routing machine fails
    if (this.simpleRouteLine) {
      this.map.removeLayer(this.simpleRouteLine);
    }

    const polyline = L.polyline(
      [[this.userLat, this.userLon], [destLat, destLon]],
      {
        color: '#8b5cf6',
        weight: 5,
        opacity: 0.8,
        dashArray: '10, 5'
      }
    ).addTo(this.map);

    this.simpleRouteLine = polyline;

    // Calculate distance using Haversine formula
    const distance = this.calculateDistance(this.userLat, this.userLon, destLat, destLon);
    
    // Show info popup
    const routeInfo = `
      <div style="padding: 8px; min-width: 200px;">
        <strong style="color: #1f2937;">Direct route to ${this.escapeHtml(destinationName || 'Destination')}</strong><br>
        <span style="color: #6b7280; font-size: 14px;">
          Straight-line distance: ${distance.toFixed(2)} km<br>
          <em>Note: This is a direct line. Actual route may vary.</em>
        </span>
      </div>
    `;

    L.popup({ maxWidth: 250 })
      .setLatLng([destLat, destLon])
      .setContent(routeInfo)
      .openOn(this.map);

    // Fit map
    this.map.fitBounds([
      [this.userLat, this.userLon],
      [destLat, destLon]
    ], { padding: [50, 50] });
  }

  calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Radius of the Earth in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  clearRoute() {
    if (this.routingControl) {
      this.map.removeControl(this.routingControl);
      this.routingControl = null;
    }
    if (this.simpleRouteLine) {
      this.map.removeLayer(this.simpleRouteLine);
      this.simpleRouteLine = null;
    }
  }

  clearMarkers() {
    this.markers.forEach(marker => {
      this.map.removeLayer(marker);
    });
    this.markers = [];
    this.clearRoute();
  }

  destroy() {
    this.clearRoute();
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
    this.markers = [];
    this.userMarker = null;
    this.userLat = null;
    this.userLon = null;
    this.simpleRouteLine = null;
  }
}

// Export for use in other scripts
window.HealthcareMap = HealthcareMap;


