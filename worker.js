// Cloudflare Worker for Find Your Team Flask App
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Handle static files
    if (url.pathname.startsWith('/static/')) {
      return fetch(request);
    }
    
    // Handle API routes
    if (url.pathname.startsWith('/api/')) {
      // Forward to your Flask app running on port 5002
      const flaskUrl = `http://localhost:5002${url.pathname}${url.search}`;
      
      const response = await fetch(flaskUrl, {
        method: request.method,
        headers: request.headers,
        body: request.body
      });
      
      return response;
    }
    
    // Handle main routes
    const flaskUrl = `http://localhost:5002${url.pathname}${url.search}`;
    return fetch(flaskUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
  },
};