FROM node:20-alpine AS build

WORKDIR /app

COPY frontend-react/package.json /app/package.json
COPY frontend-react/pnpm-lock.yaml /app/pnpm-lock.yaml
RUN npm install

COPY frontend-react /app
RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache bash

COPY deploy/aws/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/aws/frontend-entrypoint.sh /docker-entrypoint.d/40-render-runtime-config.sh
COPY --from=build /app/dist /usr/share/nginx/html

RUN chmod +x /docker-entrypoint.d/40-render-runtime-config.sh

EXPOSE 80
