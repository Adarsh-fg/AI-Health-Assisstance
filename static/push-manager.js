console.log("push-manager.js: Script started.");

async function runPushManager() {
    // Check for VAPID key first
    const VAPID_PUBLIC_KEY = window.vapidPublicKey;
    if (!VAPID_PUBLIC_KEY) {
        console.error("push-manager.js: VAPID_PUBLIC_KEY not found on window object. Aborting.");
        return;
    }
    console.log("push-manager.js: VAPID key found.");

    try {
        // Register the service worker from the root path
        console.log("push-manager.js: Attempting to register service worker at /service-worker.js");
        const registration = await navigator.serviceWorker.register('/service-worker.js');
        console.log('push-manager.js: Service Worker registration successful. Scope:', registration.scope);

        // ... (The rest of the subscription and fetch logic from the previous step is fine)
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            console.warn('push-manager.js: Notification permission was not granted.');
            return;
        }
        console.log('push-manager.js: Notification permission granted.');

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
        });
        console.log('push-manager.js: User subscription successful.');

        const response = await fetch('/save-subscription', {
            method: 'POST',
            body: JSON.stringify(subscription),
            headers: { 'content-type': 'application/json' }
        });

        if (response.ok) {
            console.log('push-manager.js: Subscription sent to server successfully.');
        } else {
            console.error('push-manager.js: Failed to send subscription to server.');
        }

    } catch (err) {
        console.error('push-manager.js: A critical error occurred in runPushManager: ', err);
    }
}

// Utility function to convert key
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) { outputArray[i] = rawData.charCodeAt(i); }
    return outputArray;
}


if ('serviceWorker' in navigator && 'PushManager' in window) {
    // Run after the entire page is loaded to ensure window.vapidPublicKey is set
    window.addEventListener('load', runPushManager);
} else {
    console.warn('push-manager.js: This browser does not support push notifications.');
}