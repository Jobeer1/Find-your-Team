// Find Your Team - Service Worker for Offline Functionality
// Enables the platform to work in low-bandwidth and offline conditions

const CACHE_NAME = 'find-your-team-v1';
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/templates/find_your_team.html',
  'https://code.jquery.com/jquery-3.6.0.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css'
];

// Install event - cache resources
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Return cached version or fetch from network
        if (response) {
          return response;
        }
        
        // Clone the request because it's a stream
        const fetchRequest = event.request.clone();
        
        return fetch(fetchRequest).then(function(response) {
          // Check if valid response
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // Clone the response because it's a stream
          const responseToCache = response.clone();
          
          caches.open(CACHE_NAME)
            .then(function(cache) {
              cache.put(event.request, responseToCache);
            });
          
          return response;
        }).catch(function() {
          // Return offline page or cached content
          if (event.request.destination === 'document') {
            return caches.match('/');
          }
        });
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Background sync for offline message queuing
self.addEventListener('sync', function(event) {
  if (event.tag === 'background-sync') {
    event.waitUntil(syncOfflineMessages());
  }
});

// Handle offline message queuing
function syncOfflineMessages() {
  return new Promise(function(resolve, reject) {
    // Get queued messages from IndexedDB
    const request = indexedDB.open('FindYourTeamDB', 1);
    
    request.onsuccess = function(event) {
      const db = event.target.result;
      const transaction = db.transaction(['messages'], 'readonly');
      const store = transaction.objectStore('messages');
      const getAllRequest = store.getAll();
      
      getAllRequest.onsuccess = function() {
        const messages = getAllRequest.result;
        
        // Send each queued message
        const promises = messages.map(message => {
          return fetch('/api/onboard', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(message)
          }).then(response => {
            if (response.ok) {
              // Remove from queue after successful send
              const deleteTransaction = db.transaction(['messages'], 'readwrite');
              const deleteStore = deleteTransaction.objectStore('messages');
              deleteStore.delete(message.id);
            }
          });
        });
        
        Promise.all(promises).then(() => resolve()).catch(() => reject());
      };
    };
    
    request.onerror = function() {
      reject();
    };
  });
}

// Push notification handling
self.addEventListener('push', function(event) {
  const options = {
    body: event.data ? event.data.text() : 'New team opportunity available!',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Explore',
        icon: '/static/icon-192.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/static/icon-192.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('Find Your Team', options)
  );
});

// Notification click handling
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});