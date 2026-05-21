# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS build

ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG VITE_BASE_PATH=/PubSync/

WORKDIR /app

COPY package.json ./
RUN npm install --registry="${NPM_REGISTRY}"

COPY . .
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
