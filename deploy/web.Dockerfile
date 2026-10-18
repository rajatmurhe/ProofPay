FROM node:22-bookworm-slim
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
# Next rewrites are fixed during build; point at the private Compose service.
ARG API_URL=http://api:8017
ENV API_URL=$API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build && chown -R node:node /app
ENV NODE_ENV=production
USER node
EXPOSE 3017
CMD ["./node_modules/.bin/next", "start", "--hostname", "0.0.0.0", "--port", "3017"]
