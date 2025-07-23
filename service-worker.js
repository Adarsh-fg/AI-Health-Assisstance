// In static/js/service-worker.js

console.log("Service Worker Loaded");

self.addEventListener('push', e => {
    const data = e.data.json();
    console.log("Push Received...");
    self.registration.showNotification(data.title, {
        body: data.body,
        icon: 'https://img.icons8.com/fluency/48/heart-with-pulse.png' // Your app's icon
    });
});