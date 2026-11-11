# Build the static app, then serve it with nginx, which also proxies /api, /ws and /media.
# Pin both base images by digest before deploying anywhere public.
FROM node:24-slim AS build
WORKDIR /web
COPY package.json package-lock.json .npmrc ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
