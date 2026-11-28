# خدمة توقيع IPA — تعمل على Cloud Run / Fly.io / أي مضيف حاويات. لا تعمل على Cloudflare Pages Functions.
FROM debian:bookworm-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git ca-certificates libssl-dev zlib1g-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN git clone --depth 1 https://github.com/zhlynn/zsign.git
WORKDIR /build/zsign
# راجع README الرسمي لو تغيّر أمر البناء مستقبلاً؛ لم يُختبر هذا السطر هنا (لا توجد شبكة في بيئة التطوير).
RUN make

FROM node:20-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends libssl3 zlib1g ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/zsign/zsign /usr/local/bin/zsign
RUN chmod +x /usr/local/bin/zsign
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev
COPY src ./src
ENV NODE_ENV=production PORT=8080
EXPOSE 8080
CMD ["node", "src/server.js"]
