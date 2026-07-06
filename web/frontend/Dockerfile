# Frontend ZefiroSplit — build Vite + nginx com proxy /api → backend
# Build context: raiz do repositório
#   docker build -f web/frontend/Dockerfile .
FROM node:20-alpine AS build

WORKDIR /fe
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci

COPY web/frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY web/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /fe/dist /usr/share/nginx/html
EXPOSE 80
