/** @type {import('next').NextConfig} */
const nextConfig = {
  /* config options here */
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*',
      },
      {
        source: '/media/:path*',
        destination: 'http://backend:8000/media/:path*',
      }
    ];
  },
};

export default nextConfig;
