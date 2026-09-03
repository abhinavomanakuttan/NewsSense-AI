/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
  async rewrites() {
    const rawBackend =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    const backendHost = rawBackend.replace(/\/api\/v1\/?$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendHost}/api/v1/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${backendHost}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
