# خدمة توقيع IPA — تعمل على Render/Cloud Run/Fly.io/أي مضيف حاويات. لا تعمل على Cloudflare Pages Functions.
FROM debian:bookworm-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    git g++ make pkg-config libssl-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN git clone --depth 1 https://github.com/zhlynn/zsign.git
WORKDIR /build/zsign/build/linux
RUN make clean && make

FROM node:20-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends libssl3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/zsign/bin/zsign /usr/local/bin/zsign
RUN chmod +x /usr/local/bin/zsign
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev
COPY src ./src
ENV NODE_ENV=production PORT=8080
EXPOSE 8080
CMD ["node", "src/server.js"]
