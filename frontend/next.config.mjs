// The browser talks only to this site; /api/* is forwarded to the Django backend (no CORS needed).
const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export default {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};
